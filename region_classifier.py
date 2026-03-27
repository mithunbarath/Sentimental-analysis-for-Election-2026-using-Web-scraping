"""
Region classifier for Tamil Nadu districts.

Maps text to one of the 39 districts in Tamil Nadu, and groups those
districts into 5 major zones (Western, Northern, Southern, Eastern, Central).
"""

import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# TN Districts mapped to Zones
# Format: "zone_name": { "district_name": ["keyword1", "keyword2", ...] }
_TN_REGIONS = {
    "western": {
        "tiruppur": ["tiruppur", "tirupur", "திருப்பூர்", "palladam", "பல்லடம்", "kangeyam", "காங்கேயம்", "dharapuram", "தாராபுரம்", "avinashi", "அவினாசி", "avanashi", "அவணாசி", "udumalaipettai", "உடுமலைப்பேட்டை"],
        "coimbatore": ["coimbatore", "kovai", "கோயம்புத்தூர்", "கோவை", "pollachi", "பொள்ளாச்சி"],
        "erode": ["erode", "ஈரோடு", "bhavani", "பவானி", "gobichettipalayam", "கோபிச்செட்டிப்பாளையம்", "sathyamangalam", "சத்தியமங்கலம்"],
        "salem": ["salem", "சேலம்", "edappadi", "எடப்பாடி", "mettur", "மேட்டூர்", "attur", "ஆத்தூர்", "omalur", "ஓமலூர்"],
        "namakkal": ["namakkal", "நாமக்கல்", "tiruchengode", "திருச்செங்கோடு", "rasipuram", "ராசிபுரம்", "paramathi vellore"],
        "dharmapuri": ["dharmapuri", "தருமபுரி", "pennagaram", "பெண்ணாகரம்", "harur", "அரூர்", "palacode"],
        "krishnagiri": ["krishnagiri", "கிருஷ்ணகிரி", "hosur", "ஓசூர்", "bargur", "பர்கூர்", "uthangarai", "ஊத்தங்கரை"],
        "the_nilgiris": ["nilgiris", "நீலகிரி", "ooty", "ஊட்டி", "udagamandalam", "உதகமண்டலம்", "coonoor", "குன்னூர்", "gudalur", "கூடலூர்", "kothagiri", "கோத்தகிரி"],
        "tirupattur": ["tirupattur", "திருப்பத்தூர்", "vaniyambadi", "வாணியம்பாடி", "ambur", "ஆம்பூர்", "jolarpet"],
    },
    "northern": {
        "chennai": ["chennai", "madras", "சென்னை", "tambaram", "தாம்பரம்", "avadi", "ஆவடி"],
        "chengalpattu": ["chengalpattu", "செங்கல்பட்டு", "mamallapuram", "மாமல்லபுரம்", "tambaram"],
        "kancheepuram": ["kancheepuram", "kanchipuram", "காஞ்சிபுரம்", "sriperumbudur"],
        "tiruvallur": ["tiruvallur", "திருவள்ளூர்", "ponneri", "gummudipoondi", "thiruvallur", "thiruttani"],
        "vellore": ["vellore", "வேலூர்", "katpadi", "காட்பாடி", "gudiyatham"],
        "ranipet": ["ranipet", "ராணிப்பேட்டை", "arakkonam", "அரக்கோணம்", "walajapet", "வாலாஜாபேட்டை", "arcode"],
        "tiruvannamalai": ["tiruvannamalai", "thiruvannamalai", "திருவண்ணாமலை", "arani", "polur", "chengam", "vandavasi", "cheyyar"],
        "viluppuram": ["viluppuram", "villupuram", "விழுப்புரம்", "tindivanam", "திண்டிவனம்", "gingee", "செஞ்சி", "vanur"],
        "kallakurichi": ["kallakurichi", "கள்ளக்குறிச்சி", "ulundurpet", "உளுந்தூர்பேட்டை", "sankarapuram", "rishivandiyam"],
    },
    "southern": {
        "madurai": ["madurai", "மதுரை", "usilampatti", "melur", "thirumangalam", "sholavandan"],
        "virudhunagar": ["virudhunagar", "விருதுநகர்", "sivakasi", "சிவகாசி", "aruppukottai", "srivilliputhur", "rajapalayam", "sattur"],
        "theni": ["theni", "தேனி", "periyakulam", "bodinayakanur", "cumbum", "andipatti"],
        "dindigul": ["dindigul", "திண்டுக்கல்", "palani", "பழனி", "oddanchatram", "kodaikanal", "nilakottai"],
        "ramanathapuram": ["ramanathapuram", "ramnad", "ராமநாதபுரம்", "paramakudi", "rameswaram", "kilakarai", "tiruvadanai", "mudukulathur"],
        "sivaganga": ["sivaganga", "சிவகங்கை", "karaikudi", "காரைக்குடி", "tiruppattur", "thiruppuvanam", "manamadurai"],
        "thoothukudi": ["thoothukudi", "tuticorin", "தூத்துக்குடி", "kovilpatti", "tiruchendur", "vilathikulam", "ottapidaram"],
        "tirunelveli": ["tirunelveli", "nellai", "திருநெல்வேலி", "ambasamudram", "palayamkottai", "radhapuram"],
        "tenkasi": ["tenkasi", "தென்காசி", "sankarankovil", "kadayanallur", "puliyangudi", "surandai"],
        "kanyakumari": ["kanyakumari", "கன்னியாகுமரி", "nagercoil", "நாகர்கோவில்", "padmanabhapuram", "colachel"],
    },
    "central": {
        "tiruchirappalli": ["tiruchirappalli", "trichy", "திருச்சிராப்பள்ளி", "திருச்சி", "srirangam", "manapparai", "musiri", "lalgudi"],
        "karur": ["karur", "கரூர்", "kulithalai", "aravakurichi"],
        "ariyalur": ["ariyalur", "அரியலூர்", "jayankondam", "sendurai"],
        "perambalur": ["perambalur", "பெரம்பலூர்", "kunnam"],
        "pudukkottai": ["pudukkottai", "புதுக்கோட்டை", "aranthangi", "thirumayam", "gandarvakottai"],
    },
    "eastern": {
        "thanjavur": ["thanjavur", "tanjore", "தஞ்சாவூர்", "kumbakonam", "கும்பகோணம்", "pattukkottai", "orathanadu", "peravurani"],
        "thiruvarur": ["thiruvarur", "திருவாரூர்", "mannargudi", "மன்னார்குடி", "thiruthuraipoondi", "nannilam"],
        "nagapattinam": ["nagapattinam", "நாகப்பட்டினம்", "kilvelur", "vedaranyam"],
        "mayiladuthurai": ["mayiladuthurai", "மயிலாடுதுறை", "sirkazhi", "சீர்காழி"],
        "cuddalore": ["cuddalore", "கடலூர்", "chidambaram", "சிதம்பரம்", "neyveli", "vriddhachalam", "panruti", "kurinjipadi", "tittakudi"],
    }
}

# Generic TN keywords
_TN_GENERAL = [
    "tamil nadu", "tamilnadu", "தமிழ்நாடு", 
    "tn politics", "tn assembly",
]

class TamilNaduRegionClassifier:
    """Classifies text into a specific Tamil Nadu district and zone."""

    def __init__(self):
        self._compiled_patterns = {}
        self._district_to_zone = {}
        self._general_pattern = self._compile_pattern(_TN_GENERAL)
        
        # Build optimized regex patterns for each district
        for zone, districts in _TN_REGIONS.items():
            for district, keywords in districts.items():
                self._compiled_patterns[district] = self._compile_pattern(keywords)
                self._district_to_zone[district] = zone

    def _compile_pattern(self, keywords: List[str]) -> re.Pattern:
        """Compile a regex pattern from a list of keywords."""
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = r"(?i)(?:\b|)(?:" + "|".join(escaped_keywords) + r")(?:\b|$)"
        return re.compile(pattern, re.UNICODE)

    def classify_region(self, text: Optional[str]) -> str:
        """
        Identify the most likely district mentioned in the text.
        Returns the district name, 'tamil_nadu_general', or 'unknown'.
        If multiple match, returns the first one found (could be enhanced with counts).
        """
        if not text:
            return "unknown"

        # Check districts
        matches = []
        for district, pattern in self._compiled_patterns.items():
            if pattern.search(text):
                matches.append(district)

        if matches:
            # If multiple districts match, returning the first one is a simple heuristic.
            # (Could improve by counting occurrences and returning max).
            # We prioritize explicit Tiruppur/Palladam matching if present to preserve existing behavior.
            if "tiruppur" in matches:
                return "tiruppur"
            return matches[0]

        # Check general TN keywords if no specific district matched
        if self._general_pattern.search(text):
            return "tamil_nadu_general"

        return "unknown"

    def get_zone(self, district: str) -> str:
        """Returns the zone (western, northern, etc) for a given district."""
        if district in ["tamil_nadu_general", "unknown"]:
            return district
        return self._district_to_zone.get(district, "unknown")
