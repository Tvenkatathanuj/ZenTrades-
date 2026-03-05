# Changelog: Coastal Sprinkler and Fire
## v1 -> v2

**Account ID:** acct_coastal_sprinkler_an_ef18be42  
**Date:** 2026-03-04T10:26:23.708525Z  
**Total Changes:** 17

---

## Summary
v1 -> v2 update: 17 total changes. Business Info: 1 change(s); Hours And Schedule: 3 change(s); Services: 1 change(s); Emergency Config: 3 change(s); Transfer Config: 2 change(s); Integration: 1 change(s); Other: 6 change(s)

---

## Changes by Category

### Business Info

- **[MODIFIED]** `office_address`
  - Before: 
  - After: 3100 Shore Drive, Suite 12, Virginia Beach, Virginia 23451

### Hours And Schedule

- **[MODIFIED]** `business_hours.days`
  - Before: 
  - After: Monday through Friday

- **[MODIFIED]** `business_hours.end`
  - Before: 
  - After: 4:30 PM

- **[MODIFIED]** `business_hours.start`
  - Before: 
  - After: 8:00 AM

### Services

- **[MODIFIED]** `services_supported`
  - Before: ["Fire Alarm Systems", "Fire Pump Services", "Fire Sprinkler Systems", "Inspection Services", "Installation", "Repair Services", "Sprinkler Systems", "Standpipe Systems", "Testing & Certification"]
  - After: ["24/7 Emergency Response", "Backflow Prevention", "Fire Alarm Systems", "Fire Protection", "Fire Pump Services", "Fire Sprinkler Systems", "Inspection Services", "Installation", "Maintenance", "Repair Services", "Sprinkler Systems", "Standpipe Systems", "Testing & Certification"]

### Emergency Config

- **[MODIFIED]** `emergency_definition`
  - Before: ["Active fire situation", "Water damage", "water damage"]
  - After: ["Active fire situation", "Flooding", "Water damage", "flooding", "water damage", "water flowing"]

- **[MODIFIED]** `emergency_routing_rules.fallback`
  - Before: Leave voicemail and assure callback
  - After: Notify dispatch team

- **[MODIFIED]** `emergency_routing_rules.who_to_call`
  - Before: [{"name": "On-call technician"}, {"name": "receptionist"}]
  - After: [{"name": "owner"}, {"name": "office manager"}]

### Transfer Config

- **[MODIFIED]** `call_transfer_rules.failure_message`
  - Before: I wasn't able to connect you directly. Let me take your information and someone will call you back shortly.
  - After: I wasn't able to reach the on-call technician directly. I'll dispatch your request and someone will contact you as soon as possible.

- **[MODIFIED]** `call_transfer_rules.timeout_seconds`
  - Before: null
  - After: 45

### Integration

- **[MODIFIED]** `integration_constraints`
  - Before: []
  - After: ["Never create certain job types in ServiceTrade (confirm specific types)", "Never create sprinkler jobs in ServiceTrade"]

### Other

- **[MODIFIED]** `after_hours_flow_summary`
  - Before: Caller reaches Clara after business hours. Clara greets the caller and acknowledges after-hours status. Clara asks for the purpose of the call. Clara determines if this is an emergency. If EMERGENCY: Clara immediately collects name, callback number, and location/address. Clara attempts to transfer to on-call personnel (On-call technician, receptionist). If transfer fails, Clara assures the caller that someone will call back shortly. If NOT EMERGENCY: Clara collects details and confirms follow-up during next business day. Clara asks if there's anything else needed. Clara closes the call.
  - After: Caller reaches Clara after business hours. Clara greets the caller and acknowledges after-hours status. Clara asks for the purpose of the call. Clara determines if this is an emergency. If EMERGENCY: Clara immediately collects name, callback number, and location/address. Clara attempts to transfer to on-call personnel (owner, office manager). If transfer fails, Clara assures the caller that someone will call back shortly. If NOT EMERGENCY: Clara collects details and confirms follow-up during next business day. Clara asks if there's anything else needed. Clara closes the call.

- **[MODIFIED]** `notes`
  - Before: 
  - After: Phone numbers mentioned: 757-555-0148, 757-555-0163, 757-555-0100, 757-555-0192

- **[MODIFIED]** `office_hours_flow_summary`
  - Before: Caller reaches Clara during business hours. Clara greets the caller professionally. Clara asks for the purpose of the call. Clara collects the caller's name and callback number. Clara attempts to transfer to appropriate party (On-call technician, receptionist). If transfer fails, Clara takes a detailed message and confirms follow-up. Clara asks if there's anything else needed. Clara closes the call professionally.
  - After: Caller reaches Clara during business hours. Clara greets the caller professionally. Clara asks for the purpose of the call. Clara collects the caller's name and callback number. Clara attempts to transfer to appropriate party (owner, office manager). If transfer fails, Clara takes a detailed message and confirms follow-up. Clara asks if there's anything else needed. Clara closes the call professionally.

- **[MODIFIED]** `questions_or_unknowns`
  - Before: ["Office address not provided"]
  - After: []

- **[MODIFIED]** `source_type`
  - Before: demo
  - After: onboarding

- **[MODIFIED]** `version`
  - Before: v1
  - After: v2

## Resolved Unknowns

- [OK] Office address not provided

---
*Generated by Clara Answers Pipeline*
