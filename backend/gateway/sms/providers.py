import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass

from django.conf import settings


class SmsProviderError(Exception):
    pass


class SmsProvider(ABC):
    name = ""

    @abstractmethod
    def send(self, recipients, body):
        raise NotImplementedError

    @abstractmethod
    def status(self, batch_id):
        raise NotImplementedError

    @abstractmethod
    def get_quota(self):
        raise NotImplementedError


class SimulatorProvider(SmsProvider):
    name = "simulator"

    def send(self, recipients, body):
        return {
            "batch_id": f"sim-{uuid.uuid4().hex}",
            "recipients": list(recipients),
        }

    def status(self, batch_id):
        return {"batch_id": batch_id, "status": "DELIVERED"}

    def get_quota(self):
        return {"remaining": None, "provider": self.name}


class VendelProvider(SmsProvider):
    name = "vendel"

    def __init__(self, client=None):
        if client is None:
            if not settings.VENDEL_API_KEY:
                raise SmsProviderError("VENDEL_API_KEY is not configured.")
            if not settings.VENDEL_API_KEY.startswith("vk_"):
                raise SmsProviderError(
                    "VENDEL_API_KEY must be an integration key starting with vk_."
                )
            try:
                from vendel_sdk import VendelClient
            except ImportError as exc:
                raise SmsProviderError(
                    "vendel-sdk is not installed. Install backend requirements."
                ) from exc
            client = VendelClient(settings.VENDEL_BASE_URL, settings.VENDEL_API_KEY)
        self.client = client

    def send(self, recipients, body):
        result = self.client.send_sms(list(recipients), body)
        if is_dataclass(result):
            result = asdict(result)
        if not isinstance(result, dict) or not result.get("batch_id"):
            raise SmsProviderError("Vendel returned no batch ID.")
        return result

    def status(self, batch_id):
        result = self.client.get_batch_status(batch_id)
        return asdict(result) if is_dataclass(result) else result

    def get_quota(self):
        result = self.client.get_quota()
        return asdict(result) if is_dataclass(result) else result


def get_sms_provider(provider_name=None):
    provider_name = provider_name or settings.SMS_PROVIDER
    if provider_name == "vendel":
        return VendelProvider()
    if provider_name == "simulator":
        return SimulatorProvider()
    raise SmsProviderError(f"Unsupported SMS provider: {provider_name}.")
