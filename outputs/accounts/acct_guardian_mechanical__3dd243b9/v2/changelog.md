# Changelog: Guardian Mechanical
## v1 -> v2

**Account ID:** acct_guardian_mechanical__3dd243b9  
**Date:** 2026-03-04T10:26:23.785328Z  
**Total Changes:** 19

---

## Summary
v1 -> v2 update: 19 total changes. Business Info: 3 change(s); Hours And Schedule: 4 change(s); Emergency Config: 4 change(s); Transfer Config: 2 change(s); Other: 6 change(s)

---

## Changes by Category

### Business Info

- **[MODIFIED]** `business_type`
  - Before: plumbing
  - After: mechanical

- **[MODIFIED]** `company_name`
  - Before: Guardian Mechanical Services
  - After: Guardian Mechanical

- **[MODIFIED]** `office_address`
  - Before: 
  - After: 889 Commerce Drive, Elk Grove Village, Illinois 60007

### Hours And Schedule

- **[MODIFIED]** `business_hours.days`
  - Before: 
  - After: Monday through Friday

- **[MODIFIED]** `business_hours.end`
  - Before: 
  - After: 4:30 PM

- **[MODIFIED]** `business_hours.start`
  - Before: 
  - After: 7:00 AM

- **[MODIFIED]** `business_hours.timezone`
  - Before: 
  - After: Central

### Emergency Config

- **[MODIFIED]** `emergency_definition`
  - Before: ["Gas leak", "No A/C (summer emergency)", "No heat (winter emergency)", "no heat", "things like no heat in winter \u2014 that's a big one for commercial buildings, it can freeze pipes"]
  - After: ["Gas leak", "No A/C (summer emergency)", "No cooling", "No heat", "No heat (winter emergency)", "gas smell", "no heat", "things like no heat in winter \u2014 that's a big one for commercial buildings, it can freeze pipes"]

- **[MODIFIED]** `emergency_routing_rules.fallback`
  - Before: Leave voicemail and assure callback
  - After: Notify dispatch team

- **[MODIFIED]** `emergency_routing_rules.who_to_call`
  - Before: [{"name": "On-call technician"}]
  - After: [{"name": "On-call technician"}, {"name": "owner"}, {"name": "office manager"}, {"name": "dispatcher"}]

- **[MODIFIED]** `non_emergency_routing_rules.during_hours`
  - Before: 
  - After: Transfer to office/front desk

### Transfer Config

- **[MODIFIED]** `call_transfer_rules.failure_message`
  - Before: I wasn't able to connect you directly. Let me take your information and someone will call you back shortly.
  - After: I wasn't able to reach the on-call technician directly. I'll dispatch your request and someone will contact you as soon as possible.

- **[MODIFIED]** `call_transfer_rules.timeout_seconds`
  - Before: null
  - After: 45

### Other

- **[MODIFIED]** `after_hours_flow_summary`
  - Before: Caller reaches Clara after business hours. Clara greets the caller and acknowledges after-hours status. Clara asks for the purpose of the call. Clara determines if this is an emergency. If EMERGENCY: Clara immediately collects name, callback number, and location/address. Clara attempts to transfer to on-call personnel (On-call technician). If transfer fails, Clara assures the caller that someone will call back shortly. If NOT EMERGENCY: Clara collects details and confirms follow-up during next business day. Clara asks if there's anything else needed. Clara closes the call.
  - After: Caller reaches Clara after business hours. Clara greets the caller and acknowledges after-hours status. Clara asks for the purpose of the call. Clara determines if this is an emergency. If EMERGENCY: Clara immediately collects name, callback number, and location/address. Clara attempts to transfer to on-call personnel (On-call technician, owner, office manager, dispatcher). If transfer fails, Clara assures the caller that someone will call back shortly. If NOT EMERGENCY: Clara collects details and confirms follow-up during next business day. Clara asks if there's anything else needed. Clara closes the call.

- **[MODIFIED]** `notes`
  - Before: 
  - After: Phone numbers mentioned: 847-555-0301, 847-555-0177, 847-555-0188, 847-555-0300

- **[MODIFIED]** `office_hours_flow_summary`
  - Before: Caller reaches Clara during business hours. Clara greets the caller professionally. Clara asks for the purpose of the call. Clara collects the caller's name and callback number. Clara attempts to transfer to appropriate party (On-call technician). If transfer fails, Clara takes a detailed message and confirms follow-up. Clara asks if there's anything else needed. Clara closes the call professionally.
  - After: Caller reaches Clara during business hours. Clara greets the caller professionally. Clara asks for the purpose of the call. Clara collects the caller's name and callback number. Clara attempts to transfer to appropriate party (On-call technician, owner, office manager, dispatcher). If transfer fails, Clara takes a detailed message and confirms follow-up. Clara asks if there's anything else needed. Clara closes the call professionally.

- **[MODIFIED]** `questions_or_unknowns`
  - Before: ["Timezone not specified", "Office address not provided"]
  - After: []

- **[MODIFIED]** `source_type`
  - Before: demo
  - After: onboarding

- **[MODIFIED]** `version`
  - Before: v1
  - After: v2

## Resolved Unknowns

- [OK] Office address not provided
- [OK] Timezone not specified

---
*Generated by Clara Answers Pipeline*
