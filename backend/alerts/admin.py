from django.contrib import admin

from .models import Alert, AlertDelivery, Rule, RuleWardPriority

admin.site.register((Rule, Alert, AlertDelivery, RuleWardPriority))
