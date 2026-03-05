"""
Account Memo Extraction Engine.

Extracts structured account information from call transcripts.
Supports two modes:
1. LLM-based extraction (using Ollama - free local LLM)
2. Rule-based extraction (zero-dependency fallback)

Both modes produce the same Account Memo JSON schema.
"""

import os
import re
import json
import logging
import argparse
from pathlib import Path
from typing import Optional

from utils import (
    generate_account_id, get_account_dir, save_json, load_json,
    load_template, create_processing_log, detect_call_type,
    BASE_DIR, TEMPLATES_DIR
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# Schema Definition
# ============================================================

EMPTY_MEMO = {
    "account_id": "",
    "company_name": "",
    "business_type": "",
    "business_hours": {
        "days": "",
        "start": "",
        "end": "",
        "timezone": ""
    },
    "office_address": "",
    "services_supported": [],
    "emergency_definition": [],
    "emergency_routing_rules": {
        "who_to_call": [],
        "call_order": [],
        "fallback": ""
    },
    "non_emergency_routing_rules": {
        "during_hours": "",
        "after_hours": ""
    },
    "call_transfer_rules": {
        "timeout_seconds": None,
        "max_retries": None,
        "failure_message": ""
    },
    "integration_constraints": [],
    "after_hours_flow_summary": "",
    "office_hours_flow_summary": "",
    "questions_or_unknowns": [],
    "notes": "",
    "source_type": "",
    "version": "v1",
    "extraction_method": ""
}


# ============================================================
# Rule-Based Extraction (Zero-Cost Fallback)
# ============================================================

class RuleBasedExtractor:
    """
    Extracts account information from transcripts using regex patterns
    and heuristic rules. No LLM required.
    """

    def __init__(self):
        self.patterns = self._build_patterns()

    def _build_patterns(self) -> dict:
        """Build regex patterns for information extraction."""
        return {
            "company_name": [
                r"(?:company|business|we are|this is|i'm with|we're)\s+(?:called\s+)?([A-Z][A-Za-z\s&']+(?:LLC|Inc|Corp|Co|Services|Solutions|Electric|Plumbing|HVAC|Fire|Protection|Mechanical|Sprinkler)?)",
                r"(?:welcome to|thank you for calling)\s+([A-Z][A-Za-z\s&']+)",
                r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+(?:fire protection|electric|plumbing|hvac|mechanical|sprinkler|services)",
            ],
            "business_hours": [
                r"(?:business hours|office hours|we(?:'re| are) open)\s*(?:are|from)?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\s*(?:to|until|-|through)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))",
                r"(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\s*(?:to|until|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)",
                r"(?:Monday|Mon)\s*(?:through|to|-|thru)\s*(?:Friday|Fri)\s*,?\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))\s*(?:to|until|-)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM))",
            ],
            "days": [
                r"(Monday\s*(?:through|to|-|thru)\s*(?:Friday|Saturday|Sunday))",
                r"((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:\s*-\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)))",
                r"(seven days a week|7 days a week|every day|weekdays|weekdays only)",
            ],
            "timezone": [
                r"\b(Eastern|Central|Mountain|Pacific)\s*(?:time|timezone|time zone)?\b",
                r"\b(EST|CST|MST|PST|EDT|CDT|MDT|PDT)\b",
            ],
            "address": [
                r"(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl)[.,]?\s*(?:Suite|Ste|Unit|#)?\s*\d*[.,]?\s*[A-Za-z\s]+[.,]?\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
                r"(?:address|located at|we're at|office is at)\s*(?:is\s*)?:?\s*(.+?)(?:\.|$)",
            ],
            "services": [
                r"(?:fire protection|fire alarm|fire sprinkler|sprinkler system|fire extinguisher|suppression system|hood system|backflow|inspection|testing|maintenance|install|repair|emergency service|24.?7|monitoring|alarm monitoring|extinguisher service|hydrant|standpipe|fire pump|kitchen hood|clean agent|wet chemical|dry chemical|fire door|fire damper|smoke control|emergency light)",
            ],
            "emergency_triggers": [
                r"(?:emergency|emergencies)\s*(?:is|are|means?|include|would be|defined as)\s*:?\s*(.+?)(?:\.|$)",
                r"(?:consider|treat)\s*(?:it\s*)?(?:as\s*)?(?:an?\s*)?emergency\s*(?:if|when)\s*(.+?)(?:\.|$)",
                r"(?:sprinkler\s+(?:leak|break|burst|discharge|activation)|fire\s+alarm\s+(?:going off|triggered|sounding)|flooding|water\s+(?:leak|damage|flowing)|no\s+(?:heat|ac|cooling|power)|gas\s+(?:leak|smell))",
            ],
            "phone_numbers": [
                r"(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})",
                r"(\d{3}-\d{3}-\d{4})",
            ],
            "email": [
                r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            ],
            "transfer_timeout": [
                r"(\d+)\s*(?:seconds?|sec)\s*(?:timeout|before|ring|transfer)",
                r"(?:timeout|ring|wait)\s*(?:for\s*)?(\d+)\s*(?:seconds?|sec)",
            ],
            "servicetrade_constraints": [
                r"(?:never|don't|do not|should not|shouldn't)\s+(?:create|add|put|make)\s+(.+?)\s+(?:in|into|on)\s+(?:ServiceTrade|service trade)",
                r"(?:ServiceTrade|service trade)\s+(?:should|must|needs to)\s+(.+?)(?:\.|$)",
            ],
            "routing_contacts": [
                r"(?:call|contact|reach|transfer to|dispatch|notify)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:at|on)?\s*(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})?",
                r"(?:on.?call|manager|supervisor|dispatcher|technician|owner)\s*(?:is|:)?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            ],
        }

    def extract(self, transcript: str, call_type: str = "demo") -> dict:
        """
        Extract account memo from transcript using rule-based patterns.
        
        Args:
            transcript: Full text transcript
            call_type: 'demo' or 'onboarding'
        
        Returns:
            Account memo dictionary
        """
        memo = json.loads(json.dumps(EMPTY_MEMO))  # Deep copy
        memo["source_type"] = call_type
        memo["extraction_method"] = "rule_based"
        unknowns = []

        # Extract company name
        company_name = self._extract_company_name(transcript)
        if company_name:
            memo["company_name"] = company_name
            memo["account_id"] = generate_account_id(company_name)
        else:
            unknowns.append("Company name could not be determined from transcript")

        # Extract business type
        memo["business_type"] = self._extract_business_type(transcript)

        # Extract business hours
        hours = self._extract_business_hours(transcript)
        if hours:
            memo["business_hours"] = hours
        else:
            if call_type == "demo":
                unknowns.append("Business hours not explicitly stated in demo call")

        # Extract timezone
        tz = self._extract_timezone(transcript)
        if tz:
            memo["business_hours"]["timezone"] = tz
        elif not memo["business_hours"]["timezone"]:
            unknowns.append("Timezone not specified")

        # Extract address
        address = self._extract_address(transcript)
        if address:
            memo["office_address"] = address
        else:
            unknowns.append("Office address not provided")

        # Extract services
        services = self._extract_services(transcript)
        memo["services_supported"] = services if services else []
        if not services:
            unknowns.append("Specific services not enumerated")

        # Extract emergency definitions
        emergencies = self._extract_emergency_definitions(transcript)
        memo["emergency_definition"] = emergencies
        if not emergencies and call_type == "onboarding":
            unknowns.append("Emergency definitions not clearly stated")

        # Extract routing rules
        routing = self._extract_routing_rules(transcript)
        memo["emergency_routing_rules"] = routing.get("emergency", memo["emergency_routing_rules"])
        memo["non_emergency_routing_rules"] = routing.get("non_emergency", memo["non_emergency_routing_rules"])

        # Extract transfer rules
        transfer = self._extract_transfer_rules(transcript)
        memo["call_transfer_rules"] = transfer

        # Extract integration constraints
        constraints = self._extract_integration_constraints(transcript)
        memo["integration_constraints"] = constraints

        # Generate flow summaries
        memo["office_hours_flow_summary"] = self._generate_office_hours_summary(memo)
        memo["after_hours_flow_summary"] = self._generate_after_hours_summary(memo)

        # Extract contact info / notes
        emails = re.findall(self.patterns["email"][0], transcript)
        phones = re.findall(self.patterns["phone_numbers"][0], transcript)
        notes_parts = []
        if emails:
            notes_parts.append(f"Emails mentioned: {', '.join(set(emails))}")
        if phones:
            notes_parts.append(f"Phone numbers mentioned: {', '.join(set(phones))}")
        memo["notes"] = "; ".join(notes_parts) if notes_parts else ""

        memo["questions_or_unknowns"] = unknowns
        
        return memo

    def _extract_company_name(self, transcript: str) -> Optional[str]:
        """Extract company name from transcript."""
        INDUSTRY_WORDS = r"(?:and|&|Fire|Alarm|Electric|Electrical|Mechanical|Sprinkler|Protection|Security|Services|Solutions|Contractors|HVAC|Plumbing|Pressure|Washing)"
        COMPANY_TAIL = rf"(?:[A-Z][A-Za-z]+(?:\s+{INDUSTRY_WORDS})*)"

        false_positives = {
            "Clara", "Thank", "Hello", "Please", "Let", "Good", "Hi",
            "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
            "Eastern", "Central", "Mountain", "Pacific", "ServiceTrade",
            "Service Trade", "Google", "QuickBooks", "The", "Our", "We", "My",
        }

        def _valid(name: str) -> bool:
            name = name.strip()
            return name not in false_positives and len(name) > 3 and len(name) < 80

        # Priority 0 (highest): "[Person] calling from / at / with [Company]"
        # Handles: "this is Jennifer calling from Patriot Alarm and Security"
        p0_patterns = [
            rf"calling from\s+({COMPANY_TAIL})",
            rf"(?:manager|director|owner|supervisor|tech|technician|foreman)\s+(?:at|for|of|with)\s+({COMPANY_TAIL})",
            rf"I(?:'m| am)\s+(?:\w+\s+){{0,4}}(?:at|for|with)\s+({COMPANY_TAIL})",
        ]
        for pattern in p0_patterns:
            matches = re.findall(pattern, transcript)
            if matches:
                name = matches[0].strip()
                if _valid(name):
                    return name

        # Priority 1: Explicit intro patterns
        p1_patterns = [
            rf"(?:I'm|i'm|I am|we're|we are)\s+(?:from|with|at|calling from)\s+({COMPANY_TAIL})",
            rf"(?:onboarding|setup|demo)\s+(?:for|call for|with)\s+({COMPANY_TAIL})",
        ]
        for pattern in p1_patterns:
            matches = re.findall(pattern, transcript)
            if matches:
                name = matches[0].strip()
                if _valid(name):
                    return name

        # Priority 2: Multi-word names with industry keywords (high confidence)
        p2 = rf"([A-Z][A-Za-z]+(?:\s+{INDUSTRY_WORDS})+)"
        matches = re.findall(p2, transcript)
        if matches:
            name = matches[0].strip()
            if _valid(name):
                return name

        # Priority 3: Broader "this is / welcome to" patterns
        p3_patterns = [
            rf"(?:this is|welcome to)\s+({COMPANY_TAIL})",
        ]
        for pattern in p3_patterns:
            matches = re.findall(pattern, transcript)
            if matches:
                name = matches[0].strip()
                if _valid(name) and ' ' in name:  # require multi-word to avoid person names
                    return name

        # Priority 4: Fall back to original patterns
        for pattern in self.patterns["company_name"]:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            if matches:
                name = matches[0].strip()
                name = re.sub(r'\s+$', '', name)
                if len(name) > 3 and len(name) < 80:
                    return name
        return None

    def _extract_business_type(self, transcript: str) -> str:
        """Detect the type of business from transcript."""
        t = transcript.lower()
        types = {
            "fire protection": ["fire protection", "fire alarm", "fire sprinkler", "fire extinguisher"],
            "electrical": ["electric", "electrical", "wiring", "panel"],
            "plumbing": ["plumbing", "plumber", "pipe", "drain"],
            "hvac": ["hvac", "heating", "cooling", "air conditioning", "furnace"],
            "sprinkler": ["sprinkler", "irrigation"],
            "mechanical": ["mechanical"],
            "general contractor": ["general contractor", "construction"],
            "facility maintenance": ["facility", "maintenance", "building"],
        }
        
        scores = {}
        for btype, keywords in types.items():
            scores[btype] = sum(t.count(kw) for kw in keywords)
        
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return "service business"

    def _extract_business_hours(self, transcript: str) -> dict:
        """Extract business hours from transcript."""
        hours = {"days": "", "start": "", "end": "", "timezone": ""}
        
        for pattern in self.patterns["business_hours"]:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    hours["start"] = groups[0].strip()
                    hours["end"] = groups[1].strip()
                    break
        
        for pattern in self.patterns["days"]:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                hours["days"] = match.group(1).strip()
                break
        
        if not hours["days"] and (hours["start"] or hours["end"]):
            hours["days"] = "Monday through Friday"  # Common default
        
        return hours if (hours["start"] or hours["end"]) else hours

    def _extract_timezone(self, transcript: str) -> Optional[str]:
        """Extract timezone from transcript."""
        for pattern in self.patterns["timezone"]:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                tz = match.group(1).strip()
                # Normalize
                tz_map = {
                    "ET": "Eastern", "EST": "Eastern", "EDT": "Eastern",
                    "CT": "Central", "CST": "Central", "CDT": "Central",
                    "MT": "Mountain", "MST": "Mountain", "MDT": "Mountain",
                    "PT": "Pacific", "PST": "Pacific", "PDT": "Pacific",
                }
                return tz_map.get(tz.upper(), tz)
        return None

    def _extract_address(self, transcript: str) -> Optional[str]:
        """Extract office address from transcript."""
        for pattern in self.patterns["address"]:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                return match.group(1).strip() if match.lastindex else match.group(0).strip()
        return None

    def _extract_services(self, transcript: str) -> list:
        """Extract list of services from transcript."""
        services = set()
        service_keywords = {
            "fire protection": "Fire Protection",
            "fire alarm": "Fire Alarm Systems",
            "fire sprinkler": "Fire Sprinkler Systems",
            "sprinkler system": "Sprinkler Systems",
            "fire extinguisher": "Fire Extinguisher Service",
            "suppression system": "Suppression Systems",
            "hood system": "Kitchen Hood Systems",
            "backflow": "Backflow Prevention",
            "inspection": "Inspection Services",
            "testing": "Testing & Certification",
            "maintenance": "Maintenance",
            "monitoring": "Alarm Monitoring",
            "emergency service": "Emergency Service",
            "24/7": "24/7 Emergency Response",
            "install": "Installation",
            "repair": "Repair Services",
            "hydrant": "Fire Hydrant Services",
            "standpipe": "Standpipe Systems",
            "fire pump": "Fire Pump Services",
            "kitchen hood": "Kitchen Hood Systems",
            "clean agent": "Clean Agent Systems",
            "fire door": "Fire Door Inspection",
            "fire damper": "Fire Damper Testing",
            "smoke control": "Smoke Control Systems",
            "emergency light": "Emergency Lighting",
            "electrical": "Electrical Services",
            "plumbing": "Plumbing Services",
            "hvac": "HVAC Services",
            "pressure washing": "Pressure Washing",
        }
        
        t = transcript.lower()
        for keyword, service_name in service_keywords.items():
            if keyword in t:
                services.add(service_name)
        
        return sorted(list(services))

    def _extract_emergency_definitions(self, transcript: str) -> list:
        """Extract what constitutes an emergency."""
        emergencies = set()
        
        emergency_terms = [
            ("sprinkler leak", "Sprinkler system leak"),
            ("sprinkler break", "Sprinkler system break/burst"),
            ("sprinkler discharge", "Sprinkler discharge/activation"),
            ("sprinkler activation", "Sprinkler activation"),
            ("fire alarm going off", "Fire alarm activation"),
            ("fire alarm triggered", "Fire alarm triggered"),
            ("fire alarm sounding", "Fire alarm sounding"),
            ("flooding", "Flooding"),
            ("water leak", "Water leak"),
            ("water damage", "Water damage"),
            ("gas leak", "Gas leak"),
            ("no heat", "No heat (winter emergency)"),
            ("no ac", "No A/C (summer emergency)"),
            ("no power", "Power loss"),
            ("pipe burst", "Pipe burst"),
            ("fire", "Active fire situation"),
        ]
        
        t = transcript.lower()
        for term, description in emergency_terms:
            if term in t:
                emergencies.add(description)
        
        # Also try to extract from explicit definitions
        for pattern in self.patterns["emergency_triggers"]:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            for match in matches:
                cleaned = match.strip()
                if len(cleaned) > 5 and len(cleaned) < 200:
                    emergencies.add(cleaned)
        
        # Filter out extraction artifacts (e.g., "the ADDRESS", partial phrases)
        artifact_patterns = [
            r'^the\s+[A-Z]+$',  # "the ADDRESS", "the PHONE"
            r'^[A-Z]+$',         # All-caps single words that are placeholders
        ]
        filtered = set()
        for e in emergencies:
            is_artifact = False
            for ap in artifact_patterns:
                if re.match(ap, e):
                    is_artifact = True
                    break
            if not is_artifact:
                filtered.add(e)
        
        return sorted(list(filtered))

    def _extract_routing_rules(self, transcript: str) -> dict:
        """Extract call routing rules."""
        routing = {
            "emergency": {
                "who_to_call": [],
                "call_order": [],
                "fallback": ""
            },
            "non_emergency": {
                "during_hours": "",
                "after_hours": ""
            }
        }
        
        t = transcript.lower()
        
        # Extract contacts using role-based patterns (much more precise)
        role_patterns = [
            # "on-call technician" / "our on-call guy" / "the on-call person"
            (r"(?:our|the)\s+on[- ]?call\s+(?:technician|tech|person|guy|electrician|plumber|employee|staff)", "On-call technician"),
            # "dispatch to [Name]" / "call [Name] at [phone]"
            (r"(?:dispatch|call|reach|contact|transfer to|notify)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+at\s+(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})", None),
            # "[Role] is [Name]" / "on-call is [Name]"
            (r"(?:on[- ]?call|manager|supervisor|dispatcher|owner)\s+(?:is|will be|would be)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", None),
            # "our technician / manager / dispatcher / supervisor"
            (r"(?:our|the)\s+(technician|manager|supervisor|dispatcher|foreman|owner|receptionist|office\s+(?:manager|staff))\b", None),
            # "front desk" / "main office" / "office girl" -> normalize "office girl" to "front desk"
            (r"(front desk|main office|office line|receptionist)", None),
            (r"office girl", "Front desk"),
        ]
        
        contacts_seen = set()
        # Words that look like names but aren't (verbs, adjectives, etc.)
        name_blacklist = {"panicking", "calling", "handling", "working", "looking",
                          "waiting", "coming", "going", "leaving", "trying", "running",
                          "doing", "getting", "making", "having", "being", "taking",
                          "available", "busy", "responsible", "worried", "concerned"}
        
        for pattern, default_label in role_patterns:
            matches = re.finditer(pattern, transcript, re.IGNORECASE)
            for match in matches:
                if default_label:
                    # Fixed label (e.g., "On-call technician")
                    label = default_label
                else:
                    # Use captured group
                    label = match.group(1).strip()
                    if match.lastindex and match.lastindex >= 2:
                        phone = match.group(2).strip()
                        label_key = label.lower()
                        if label_key not in contacts_seen:
                            contacts_seen.add(label_key)
                            routing["emergency"]["who_to_call"].append({"name": label, "phone": phone})
                        continue
                
                label_key = label.lower()
                if label_key not in contacts_seen and label_key not in name_blacklist:
                    contacts_seen.add(label_key)
                    routing["emergency"]["who_to_call"].append({"name": label})
        
        # If no specific contacts found, add generic based on transcript context
        if not routing["emergency"]["who_to_call"]:
            if "on-call" in t or "on call" in t:
                routing["emergency"]["who_to_call"].append({"name": "On-call technician"})
            if "dispatch" in t:
                routing["emergency"]["who_to_call"].append({"name": "Dispatch team"})
            if "front desk" in t or "receptionist" in t or "office girl" in t:
                routing["emergency"]["who_to_call"].append({"name": "Front desk / Office"})
        
        # Try to determine routing behavior
        if "phone tree" in t:
            routing["emergency"]["fallback"] = "Route to phone tree"
        elif "voicemail" in t:
            routing["emergency"]["fallback"] = "Leave voicemail and assure callback"
        elif "dispatch" in t:
            routing["emergency"]["fallback"] = "Notify dispatch team"
        elif "message" in t:
            routing["emergency"]["fallback"] = "Take a detailed message and assure callback"
        else:
            routing["emergency"]["fallback"] = "Take a detailed message and assure callback within the hour"
        
        # Non-emergency routing
        if "take a message" in t or "collect" in t:
            routing["non_emergency"]["after_hours"] = "Collect caller details and confirm follow-up during business hours"
        if "transfer" in t or "front desk" in t or "receptionist" in t:
            routing["non_emergency"]["during_hours"] = "Transfer to office/front desk"
        
        return routing

    def _extract_transfer_rules(self, transcript: str) -> dict:
        """Extract call transfer configuration."""
        rules = {
            "timeout_seconds": None,
            "max_retries": None,
            "failure_message": ""
        }
        
        for pattern in self.patterns["transfer_timeout"]:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                rules["timeout_seconds"] = int(match.group(1))
                break
        
        # Default timeout if transfer is mentioned but no timeout specified
        if rules["timeout_seconds"] is None and "transfer" in transcript.lower():
            rules["timeout_seconds"] = 30  # reasonable default
        
        # Retry detection
        retry_match = re.search(r"(\d+)\s*(?:times?|retries|attempts?|tries)", transcript, re.IGNORECASE)
        if retry_match:
            rules["max_retries"] = int(retry_match.group(1))
        
        # Failure message
        if "voicemail" in transcript.lower():
            rules["failure_message"] = "I wasn't able to connect you directly. Let me take your information and someone will call you back shortly."
        elif "dispatch" in transcript.lower():
            rules["failure_message"] = "I wasn't able to reach the on-call technician directly. I'll dispatch your request and someone will contact you as soon as possible."
        else:
            rules["failure_message"] = "I apologize, I'm unable to transfer you right now. Let me take your information and make sure someone gets back to you promptly."
        
        return rules

    def _extract_integration_constraints(self, transcript: str) -> list:
        """Extract integration constraints (e.g., ServiceTrade rules)."""
        constraints = []
        
        for pattern in self.patterns["servicetrade_constraints"]:
            matches = re.findall(pattern, transcript, re.IGNORECASE)
            for match in matches:
                constraints.append(f"ServiceTrade: {match.strip()}")
        
        # General constraint patterns
        t = transcript.lower()
        if "never create" in t and "servicetrade" in t:
            constraints.append("Never create certain job types in ServiceTrade (confirm specific types)")
        if "sprinkler" in t and "servicetrade" in t and ("never" in t or "don't" in t):
            constraints.append("Never create sprinkler jobs in ServiceTrade")
        
        return list(set(constraints))

    def _generate_office_hours_summary(self, memo: dict) -> str:
        """Generate a summary of office hours call flow."""
        parts = ["Caller reaches Clara during business hours."]
        parts.append("Clara greets the caller professionally.")
        parts.append("Clara asks for the purpose of the call.")
        parts.append("Clara collects the caller's name and callback number.")
        
        if memo["emergency_routing_rules"]["who_to_call"]:
            contacts = ", ".join(c.get("name", "team") for c in memo["emergency_routing_rules"]["who_to_call"])
            parts.append(f"Clara attempts to transfer to appropriate party ({contacts}).")
        else:
            parts.append("Clara attempts to transfer to the office.")
        
        parts.append("If transfer fails, Clara takes a detailed message and confirms follow-up.")
        parts.append("Clara asks if there's anything else needed.")
        parts.append("Clara closes the call professionally.")
        
        return " ".join(parts)

    def _generate_after_hours_summary(self, memo: dict) -> str:
        """Generate a summary of after-hours call flow."""
        parts = ["Caller reaches Clara after business hours."]
        parts.append("Clara greets the caller and acknowledges after-hours status.")
        parts.append("Clara asks for the purpose of the call.")
        parts.append("Clara determines if this is an emergency.")
        
        parts.append("If EMERGENCY: Clara immediately collects name, callback number, and location/address.")
        
        if memo["emergency_routing_rules"]["who_to_call"]:
            contacts = ", ".join(c.get("name", "on-call") for c in memo["emergency_routing_rules"]["who_to_call"])
            parts.append(f"Clara attempts to transfer to on-call personnel ({contacts}).")
        else:
            parts.append("Clara attempts to transfer to the on-call technician.")
        
        parts.append("If transfer fails, Clara assures the caller that someone will call back shortly.")
        
        parts.append("If NOT EMERGENCY: Clara collects details and confirms follow-up during next business day.")
        parts.append("Clara asks if there's anything else needed.")
        parts.append("Clara closes the call.")
        
        return " ".join(parts)


# ============================================================
# LLM-Based Extraction (Using Ollama - Free Local LLM)
# ============================================================

class OllamaExtractor:
    """
    Extracts account information using a local Ollama LLM.
    Requires Ollama to be installed and running (free, open-source).
    Falls back to rule-based extraction if Ollama is unavailable.
    """

    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.available = self._check_availability()
        if not self.available:
            logger.warning("Ollama not available. Will fall back to rule-based extraction.")

    def _check_availability(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read())
                models = [m["name"] for m in data.get("models", [])]
                if self.model not in models and f"{self.model}:latest" not in models:
                    logger.info(f"Model '{self.model}' not found. Available: {models}")
                    return False
                return True
        except Exception as e:
            logger.debug(f"Ollama check failed: {e}")
            return False

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API for text generation."""
        import urllib.request
        
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 4096,
            }
        }).encode("utf-8")
        
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read())
            return result.get("response", "")

    def extract(self, transcript: str, call_type: str = "demo") -> dict:
        """Extract account memo using Ollama LLM."""
        if not self.available:
            logger.info("Falling back to rule-based extraction")
            return RuleBasedExtractor().extract(transcript, call_type)

        prompt = self._build_extraction_prompt(transcript, call_type)
        
        try:
            response = self._call_ollama(prompt)
            memo = self._parse_llm_response(response, call_type)
            memo["extraction_method"] = f"llm_ollama_{self.model}"
            return memo
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}. Falling back to rule-based.")
            return RuleBasedExtractor().extract(transcript, call_type)

    def _build_extraction_prompt(self, transcript: str, call_type: str) -> str:
        """Build the extraction prompt for the LLM."""
        schema_str = json.dumps(EMPTY_MEMO, indent=2)
        
        return f"""You are a data extraction specialist. Extract structured information from the following {call_type} call transcript for a service business.

IMPORTANT RULES:
1. Only extract information that is EXPLICITLY stated in the transcript.
2. Do NOT invent, assume, or hallucinate any information.
3. If a field is not mentioned, leave it as an empty string, empty list, or null.
4. Add any unclear or missing items to the "questions_or_unknowns" list.
5. This is a {call_type} call - {"expect incomplete information" if call_type == "demo" else "expect more specific operational details"}.

TRANSCRIPT:
---
{transcript[:6000]}
---

Extract the information into the following JSON schema. Return ONLY valid JSON, no explanations:
{schema_str}

Return the filled JSON now:"""

    def _parse_llm_response(self, response: str, call_type: str) -> dict:
        """Parse LLM response into structured memo."""
        # Try to extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                memo = json.loads(json_match.group())
                # Validate required fields exist
                for key in EMPTY_MEMO:
                    if key not in memo:
                        memo[key] = EMPTY_MEMO[key]
                
                # Generate account_id if company_name exists
                if memo.get("company_name") and not memo.get("account_id"):
                    memo["account_id"] = generate_account_id(memo["company_name"])
                
                memo["source_type"] = call_type
                memo["version"] = "v1"
                return memo
            except json.JSONDecodeError:
                pass
        
        # Fallback to rule-based if LLM output is unparseable
        logger.warning("Could not parse LLM response. Falling back to rule-based extraction.")
        return RuleBasedExtractor().extract(response, call_type)


# ============================================================
# Main Extraction Interface
# ============================================================

def extract_account_memo(transcript: str, call_type: str = "demo", use_llm: bool = True) -> dict:
    """
    Main extraction function. Tries LLM first, falls back to rule-based.
    
    Args:
        transcript: Full text transcript of the call
        call_type: 'demo' or 'onboarding'
        use_llm: Whether to attempt LLM-based extraction
    
    Returns:
        Structured account memo dictionary
    """
    if use_llm:
        extractor = OllamaExtractor()
        if extractor.available:
            logger.info("Using Ollama LLM for extraction")
            return extractor.extract(transcript, call_type)
    
    logger.info("Using rule-based extraction")
    extractor = RuleBasedExtractor()
    return extractor.extract(transcript, call_type)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract account memo from transcript")
    parser.add_argument("transcript", help="Path to transcript file (.txt or .json)")
    parser.add_argument("-t", "--type", choices=["demo", "onboarding"], default="demo",
                        help="Call type (demo or onboarding)")
    parser.add_argument("-o", "--output", help="Output path for account memo JSON")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM, use rule-based only")
    
    args = parser.parse_args()
    
    # Load transcript
    from transcribe import load_transcript
    transcript_text = load_transcript(args.transcript)
    
    # Extract
    memo = extract_account_memo(transcript_text, args.type, use_llm=not args.no_llm)
    
    # Output
    if args.output:
        save_json(memo, args.output)
    else:
        # Save to default location
        if memo.get("account_id"):
            version = "v1" if args.type == "demo" else "v2"
            output_dir = get_account_dir(memo["account_id"], version)
            save_json(memo, output_dir / "account_memo.json")
        else:
            print(json.dumps(memo, indent=2))
    
    print(f"\n[OK] Extracted memo for: {memo.get('company_name', 'Unknown')}")
    print(f"  Account ID: {memo.get('account_id', 'N/A')}")
    print(f"  Services: {len(memo.get('services_supported', []))}")
    print(f"  Unknowns: {len(memo.get('questions_or_unknowns', []))}")
