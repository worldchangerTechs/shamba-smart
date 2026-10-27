export function normalizeKenyanPhone(value: string) {
  let digits = value.replace(/\D/g, '')
  if (digits.startsWith('254')) digits = digits.slice(3)
  if (digits.startsWith('0')) digits = digits.slice(1)
  return /^[17]\d{8}$/.test(digits) ? `+254${digits}` : null
}

export const KENYAN_PHONE_ERROR = 'Enter a Kenyan phone number like 0712 345 678.'
