"""Deterministic customer reply wording; no model-generated stock claims."""

import re

TEXT = {
    "en": {
        "received": "We received your request. Current availability check:",
        "available": "currently available",
        "insufficient_stock": "requested quantity is not currently available",
        "needs_review": "our team needs to verify the item, quantity or unit",
        "not_tracked": "our team will verify availability",
        "pending": "This is not a confirmed order or stock reservation. Our team will review it and confirm the final items, units and availability.",
        "greeting": "Hello! Please send the product name or SKU, quantity and selling unit. Our team reviews orders before confirming them.",
        "info": "Business information: ",
        "terms": "Please confirm any order-specific terms with our team.",
        "confirmed": "Our team approved your order. Reference: {reference}. Confirmed total: LKR {amount}. Delivery arrangements will be confirmed by our team.",
        "rejected": "Our team could not approve this order request. Please contact us to discuss the items or alternatives.",
    },
    "si": {
        "received": "ඔබගේ ඉල්ලීම ලැබුණා. දැනට ඇති තොග අනුව:",
        "available": "දැනට ලබාගත හැකියි",
        "insufficient_stock": "ඉල්ලූ ප්‍රමාණයට දැනට තොග ප්‍රමාණවත් නැහැ",
        "needs_review": "භාණ්ඩය, ප්‍රමාණය හෝ ඒකකය අපගේ කණ්ඩායම පරීක්ෂා කළ යුතුයි",
        "not_tracked": "ලබාදිය හැකි බව අපගේ කණ්ඩායම පරීක්ෂා කරයි",
        "pending": "මෙය තහවුරු කළ ඇණවුමක් හෝ තොග වෙන්කිරීමක් නොවේ. අපගේ කණ්ඩායම අවසන් භාණ්ඩ, ඒකක සහ ලබාදිය හැකි බව පරීක්ෂා කර තහවුරු කරයි.",
        "greeting": "ආයුබෝවන්! භාණ්ඩයේ නම හෝ SKU අංකය, ප්‍රමාණය සහ විකුණුම් ඒකකය එවන්න. ඇණවුම තහවුරු කිරීමට පෙර අපගේ කණ්ඩායම එය පරීක්ෂා කරයි.",
        "info": "ව්‍යාපාර තොරතුරු: ",
        "terms": "ඔබගේ ඇණවුමට අදාළ කොන්දේසි අපගේ කණ්ඩායම සමඟ තහවුරු කරන්න.",
        "confirmed": "අපගේ කණ්ඩායම ඔබගේ ඇණවුම අනුමත කළා. යොමු අංකය: {reference}. තහවුරු කළ මුළු මුදල: LKR {amount}. බෙදාහැරීමේ විස්තර කණ්ඩායම තහවුරු කරයි.",
        "rejected": "අපගේ කණ්ඩායමට මෙම ඇණවුම් ඉල්ලීම අනුමත කිරීමට නොහැකි වුණා. භාණ්ඩ හෝ විකල්ප ගැන සාකච්ඡා කිරීමට අප අමතන්න.",
    },
    "ta": {
        "received": "உங்கள் கோரிக்கை கிடைத்தது. தற்போதைய இருப்பு விவரம்:",
        "available": "தற்போது கிடைக்கிறது",
        "insufficient_stock": "கோரிய அளவுக்கு தற்போது இருப்பு இல்லை",
        "needs_review": "பொருள், அளவு அல்லது அலகை எங்கள் குழு சரிபார்க்க வேண்டும்",
        "not_tracked": "கிடைக்கும் நிலையை எங்கள் குழு சரிபார்க்கும்",
        "pending": "இது உறுதி செய்யப்பட்ட ஆர்டரோ இருப்பு ஒதுக்கீடோ அல்ல. எங்கள் குழு இறுதிப் பொருட்கள், அலகுகள் மற்றும் இருப்பை சரிபார்த்து உறுதி செய்யும்.",
        "greeting": "வணக்கம்! பொருளின் பெயர் அல்லது SKU, அளவு மற்றும் விற்பனை அலகை அனுப்பவும். ஆர்டரை உறுதி செய்வதற்கு முன் எங்கள் குழு சரிபார்க்கும்.",
        "info": "வணிகத் தகவல்: ",
        "terms": "உங்கள் ஆர்டருக்கான நிபந்தனைகளை எங்கள் குழுவுடன் உறுதி செய்யவும்.",
        "confirmed": "எங்கள் குழு உங்கள் ஆர்டரை அங்கீகரித்தது. குறிப்பு: {reference}. உறுதி செய்யப்பட்ட மொத்தம்: LKR {amount}. விநியோக விவரங்களை எங்கள் குழு உறுதி செய்யும்.",
        "rejected": "இந்த ஆர்டர் கோரிக்கையை எங்கள் குழுவால் அங்கீகரிக்க முடியவில்லை. பொருட்கள் அல்லது மாற்று தேர்வுகள் பற்றி பேச எங்களைத் தொடர்புகொள்ளவும்.",
    },
}


def wording(source):
    tamil = bool(re.search(r"[\u0b80-\u0bff]", source or ""))
    sinhala = bool(re.search(r"[\u0d80-\u0dff]", source or ""))
    return TEXT[
        "ta" if tamil and not sinhala else "si" if sinhala and not tamil else "en"
    ]
