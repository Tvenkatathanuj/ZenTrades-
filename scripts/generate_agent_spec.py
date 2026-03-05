"""
Retell Agent Spec Generator.

Takes an Account Memo JSON and generates a Retell Agent Draft Specification,
including the system prompt, voice settings, and configuration.
"""

import os
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

from utils import (
    get_account_dir, save_json, load_json, load_template,
    BASE_DIR, TEMPLATES_DIR
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_system_prompt(memo: dict) -> str:
    """
    Generate the system prompt for the Retell AI agent based on the account memo.
    Follows strict prompt hygiene requirements.
    """
    company = memo.get("company_name", "the company")
    biz_type = memo.get("business_type", "service business")
    # Correct grammar: use "an" before vowel sounds
    biz_article = "an" if biz_type and biz_type[0].lower() in "aeiou" else "a"
    hours = memo.get("business_hours", {})
    hours_str = ""
    if hours.get("start") and hours.get("end"):
        days = hours.get("days", "Monday through Friday")
        tz = hours.get("timezone", "")
        hours_str = f"{days}, {hours['start']} to {hours['end']}"
        if tz:
            hours_str += f" {tz}"
    
    address = memo.get("office_address", "")
    services = memo.get("services_supported", [])
    services_str = ", ".join(services) if services else "various services"
    
    emergency_defs = memo.get("emergency_definition", [])
    emergency_str = "\n".join(f"  - {e}" for e in emergency_defs) if emergency_defs else "  - Not yet defined (use general emergency criteria)"
    
    emergency_routing = memo.get("emergency_routing_rules", {})
    contacts = emergency_routing.get("who_to_call", [])
    contacts_str = ""
    if contacts:
        for i, c in enumerate(contacts, 1):
            name = c.get("name", "Contact")
            phone = c.get("phone", "")
            contacts_str += f"  {i}. {name}"
            if phone:
                contacts_str += f" ({phone})"
            contacts_str += "\n"
    else:
        contacts_str = "  - Transfer to office main line\n"
    
    fallback = emergency_routing.get("fallback", "Take a message and assure callback")
    
    non_emergency = memo.get("non_emergency_routing_rules", {})
    ne_during = non_emergency.get("during_hours", "Transfer to office")
    ne_after = non_emergency.get("after_hours", "Collect information and confirm follow-up during business hours")
    
    transfer_rules = memo.get("call_transfer_rules", {})
    timeout = transfer_rules.get("timeout_seconds") or 30
    max_retries = transfer_rules.get("max_retries") or 2
    failure_msg = transfer_rules.get("failure_message", 
        "I apologize, I'm unable to transfer you right now. Let me take your information and make sure someone gets back to you promptly.")
    
    constraints = memo.get("integration_constraints", [])
    constraints_str = "\n".join(f"  - {c}" for c in constraints) if constraints else "  - None specified"
    
    prompt = f"""You are Clara, a professional AI receptionist for {company}, {biz_article} {biz_type} company.
You handle inbound calls with warmth, efficiency, and professionalism.

============================
COMPANY INFORMATION
============================
Company: {company}
Type: {biz_type}
{"Address: " + address if address else "Address: Not yet configured"}
Services: {services_str}
{"Business Hours: " + hours_str if hours_str else "Business Hours: Not yet configured"}

============================
BUSINESS HOURS CALL FLOW
============================
When receiving calls DURING business hours{" (" + hours_str + ")" if hours_str else ""}:

1. GREET: "Thank you for calling {company}. This is Clara, how can I help you today?"

2. IDENTIFY PURPOSE: Listen to the caller's reason for calling.
   - If they need to schedule service, report an issue, or have a general inquiry, proceed.
   
3. COLLECT INFORMATION:
   - Ask for the caller's name
   - Ask for their callback number
   - Get a brief description of what they need
   Do NOT ask excessive questions. Only collect what is needed for routing.

4. ROUTE/TRANSFER:
   - Non-emergency during hours: {ne_during}
   - Attempt to transfer the call
   - Transfer timeout: {timeout} seconds
   - Maximum transfer attempts: {max_retries}
   
5. IF TRANSFER FAILS:
   - Say: "{failure_msg}"
   - Collect any additional details needed
   - Confirm that someone will follow up

6. WRAP UP:
   - "Is there anything else I can help you with today?"
   - If no: "Thank you for calling {company}. Have a great day!"

============================
AFTER-HOURS CALL FLOW
============================
When receiving calls OUTSIDE business hours:

1. GREET: "Thank you for calling {company}. You've reached us after hours. This is Clara, how can I help you?"

2. IDENTIFY PURPOSE: Ask the caller what they need help with.

3. DETERMINE EMERGENCY STATUS:
   Ask: "Is this an emergency situation?"
   
   Emergency conditions include:
{emergency_str}

4. IF EMERGENCY:
   a. Immediately collect:
      - Caller's name
      - Callback number  
      - Location/address of the emergency
      - Brief description of the situation
   
   b. Attempt emergency transfer:
      Emergency contacts (in order):
{contacts_str}
      Transfer timeout: {timeout} seconds
   
   c. If transfer succeeds: Confirm the caller has been connected.
   
   d. If transfer fails:
      - "{fallback}"
      - Assure the caller: "I've logged this as an emergency. Someone from our team will call you back as soon as possible."
      - Collect any additional relevant details

5. IF NOT EMERGENCY:
   a. Collect:
      - Caller's name
      - Callback number
      - Description of their need
   b. Confirm: "I've noted your request. Someone from our team will follow up with you during our next business day{" (" + hours_str + ")" if hours_str else ""}."

6. WRAP UP:
   - "Is there anything else I can help you with?"
   - If no: "Thank you for calling {company}. {"We'll be back in the office " + (hours.get("start", "tomorrow") if hours.get("start") else "tomorrow") + "." if True else ""} Goodbye!"

============================
CALL TRANSFER PROTOCOL
============================
When transferring a call:
1. Inform the caller: "Let me transfer you now. Please hold for a moment."
2. Initiate the transfer (timeout: {timeout} seconds)
3. If no answer after {timeout} seconds, retry up to {max_retries} time(s)
4. If all attempts fail:
   - Apologize to the caller
   - Collect their information
   - Assure follow-up
   - NEVER leave the caller without next steps

============================
INTEGRATION CONSTRAINTS
============================
{constraints_str}

============================
CRITICAL RULES
============================
1. NEVER mention internal systems, tools, functions, or technical processes to the caller.
2. NEVER say "I'm going to call a function" or reference any backend operations.
3. NEVER fabricate information. If you don't know something, say so.
4. Keep conversations efficient - collect only what is needed.
5. Always be empathetic, especially during emergencies.
6. Always provide next steps before ending a call.
7. If the caller is upset, acknowledge their frustration before proceeding.
8. Speak naturally and conversationally - avoid robotic responses.
"""
    return prompt.strip()


def generate_agent_spec(memo: dict, version: str = None) -> dict:
    """
    Generate a complete Retell Agent Draft Specification.
    
    Args:
        memo: Account memo dictionary
        version: Version string (e.g., 'v1', 'v2'). Auto-detected if None.
    
    Returns:
        Agent specification dictionary
    """
    if version is None:
        version = memo.get("version", "v1")
    
    company = memo.get("company_name", "Unknown Company")
    hours = memo.get("business_hours", {})
    
    system_prompt = generate_system_prompt(memo)
    
    spec = {
        "agent_name": f"Clara - {company}",
        "agent_id": f"agent_{memo.get('account_id', 'unknown')}_{version}",
        "version": version,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "account_id": memo.get("account_id", ""),
        
        "voice_config": {
            "voice_style": "professional_friendly",
            "voice_id": "rachel",  # Retell default professional female voice
            "language": "en-US",
            "speech_rate": 1.0,
            "pitch": 1.0,
        },
        
        "system_prompt": system_prompt,
        
        "key_variables": {
            "company_name": company,
            "business_type": memo.get("business_type", ""),
            "timezone": hours.get("timezone", ""),
            "business_hours": {
                "days": hours.get("days", ""),
                "start": hours.get("start", ""),
                "end": hours.get("end", "")
            },
            "office_address": memo.get("office_address", ""),
            "emergency_contacts": memo.get("emergency_routing_rules", {}).get("who_to_call", []),
        },
        
        "tool_invocation_placeholders": {
            "transfer_call": {
                "description": "Transfer the active call to a specified phone number",
                "parameters": {
                    "phone_number": "string - Target phone number",
                    "timeout_seconds": memo.get("call_transfer_rules", {}).get("timeout_seconds", 30),
                    "caller_name": "string - Name of the caller being transferred"
                },
                "note": "Tool invocations are NEVER mentioned to the caller"
            },
            "log_message": {
                "description": "Log a message for follow-up by the team",
                "parameters": {
                    "caller_name": "string",
                    "callback_number": "string",
                    "message_type": "emergency | non_emergency | general",
                    "message_details": "string",
                    "urgency": "high | medium | low"
                },
                "note": "Tool invocations are NEVER mentioned to the caller"
            },
            "check_business_hours": {
                "description": "Check if current time is within business hours",
                "parameters": {},
                "note": "Used internally to determine call flow"
            }
        },
        
        "call_transfer_protocol": {
            "timeout_seconds": memo.get("call_transfer_rules", {}).get("timeout_seconds", 30),
            "max_retries": memo.get("call_transfer_rules", {}).get("max_retries", 2),
            "on_success": "Confirm caller is connected",
            "on_failure": memo.get("call_transfer_rules", {}).get("failure_message", 
                "I apologize, I'm unable to transfer you right now. Let me take your information.")
        },
        
        "fallback_protocol": {
            "transfer_failure": "Collect caller info, log message, assure follow-up",
            "system_error": "Apologize, provide main office number, suggest callback",
            "unclear_input": "Politely ask caller to repeat or clarify",
            "escalation_phrases": [
                "I'd like to speak to a person",
                "Let me talk to someone",
                "Can I speak to a manager",
                "I need a human"
            ],
            "escalation_action": "Attempt immediate transfer to available staff"
        },
        
        "metadata": {
            "source_call_type": memo.get("source_type", ""),
            "extraction_method": memo.get("extraction_method", ""),
            "unknowns_count": len(memo.get("questions_or_unknowns", [])),
            "confidence_level": "preliminary" if version == "v1" else "confirmed",
        }
    }
    
    return spec


def save_agent_spec(spec: dict, account_id: str = None, version: str = None) -> Path:
    """
    Save agent spec to the appropriate output directory.
    
    Args:
        spec: Agent specification dictionary
        account_id: Account ID (auto-detected from spec if None)
        version: Version string (auto-detected from spec if None)
    
    Returns:
        Path to saved file
    """
    account_id = account_id or spec.get("account_id", "unknown")
    version = version or spec.get("version", "v1")
    
    output_dir = get_account_dir(account_id, version)
    output_path = output_dir / "agent_spec.json"
    
    save_json(spec, output_path)
    
    # Also save the system prompt as a separate readable file
    prompt_path = output_dir / "system_prompt.txt"
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(spec.get("system_prompt", ""))
    logger.info(f"System prompt saved to: {prompt_path}")
    
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Retell agent spec from account memo")
    parser.add_argument("memo", help="Path to account memo JSON file")
    parser.add_argument("-v", "--version", default=None, help="Version string (e.g., v1, v2)")
    parser.add_argument("-o", "--output", help="Output path for agent spec JSON")
    
    args = parser.parse_args()
    
    memo = load_json(args.memo)
    version = args.version or memo.get("version", "v1")
    
    spec = generate_agent_spec(memo, version)
    
    if args.output:
        save_json(spec, args.output)
    else:
        save_agent_spec(spec, memo.get("account_id"), version)
    
    print(f"\n[OK] Generated agent spec: {spec['agent_name']}")
    print(f"  Version: {version}")
    print(f"  Prompt length: {len(spec['system_prompt'])} chars")
    print(f"  Confidence: {spec['metadata']['confidence_level']}")
