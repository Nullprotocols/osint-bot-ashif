# config.py - Complete configuration for OSINT Pro Bot on Render

import os

# ==================== BOT TOKEN ====================
# Render ke environment variable se lega, nahi to placeholder
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ==================== OWNER & ADMINS ====================
OWNER_ID = 8104850849  # Owner ka Telegram user ID
INITIAL_ADMINS = [8104850849, 5987905091]  # Ye DB me automatically add honge

# ==================== FORCE JOIN CHANNELS ====================
FORCE_JOIN_CHANNELS = [
    {"name": "All Data Here", "link": "https://t.me/all_data_here", "id": -1003090922367},
    {"name": "OSINT Lookup", "link": "https://t.me/osint_lookup", "id": -1003698567122}
]

# ==================== LOG CHANNELS (per command) ====================
LOG_CHANNELS = {
    "num": -1003482423742,
    "ifsc": -1003624886596,
    "email": -1003431549612,
    "gst": -1003634866992,
    "vehicle": -1003237155636,
    "vchalan": -1003237155636,
    "pincode": -1003677285823,
    "insta": -1003498414978,
    "git": -1003576017442,
    "pak": -1003663672738,
    "ip": -1003665811220,
    "ffinfo": -1003588577282,
    "ffban": -1003521974255,
    "tg2num": -1003642820243,
    "tginfo": -1003643170105,
    "tginfopro": -1003643170105,
}

# ==================== GLOBAL BRANDING BLACKLIST ====================
GLOBAL_BLACKLIST = [
    "@patelkrish_99",
    "patelkrish_99",
    "t.me/anshapi",
    "anshapi",
    "@Kon_Hu_Mai",
    "Kon_Hu_Mai",
    "Dm to buy access",
    "Dm to buy access"
]

# ==================== COMMANDS (DYNAMIC ROUTER) ====================
COMMANDS = {
    "num": {
        "url": "https://num-free-rootx-jai-shree-ram-14-day.vercel.app/?key=lundkinger&number={}",
        "param": "number",
        "log": LOG_CHANNELS["num"],
        "extra_blacklist": [
            "dm to buy",
            "owner",
            "@kon_hu_mai",
            "Ruk ja bhencho itne m kya unlimited request lega?? Paid lena h to bolo 100-400₹ @Simpleguy444"
        ]
    },
    "tg2num": {
        "url": "https://tg2num-owner-api.vercel.app/?userid={}",
        "param": "userid",
        "log": LOG_CHANNELS["tg2num"],
        "extra_blacklist": [
            "validity",
            "hours_remaining",
            "days_remaining",
            "expires_on",
            "https://t.me/AbdulBotzOfficial",
            "@AbdulDevStoreBot",
            "@AbdulDevStoreBot",
            "credit"
        ]
    },
    "vehicle": {
        "url": "https://vehicle-info-aco-api.vercel.app/info?vehicle={}",
        "param": "vehicle",
        "log": LOG_CHANNELS["vehicle"],
        "extra_blacklist": []
    },
    "vchalan": {
        "url": "https://api.b77bf911.workers.dev/vehicle?registration={}",
        "param": "registration",
        "log": LOG_CHANNELS["vchalan"],
        "extra_blacklist": []
    },
    "ip": {
        "url": "https://abbas-apis.vercel.app/api/ip?ip={}",
        "param": "ip",
        "log": LOG_CHANNELS["ip"],
        "extra_blacklist": []
    },
    "email": {
        "url": "https://abbas-apis.vercel.app/api/email?mail={}",
        "param": "mail",
        "log": LOG_CHANNELS["email"],
        "extra_blacklist": []
    },
    "ffinfo": {
        "url": "https://official-free-fire-info.onrender.com/player-info?key=DV_M7-INFO_API&uid={}",
        "param": "uid",
        "log": LOG_CHANNELS["ffinfo"],
        "extra_blacklist": []
    },
    "ffban": {
        "url": "https://abbas-apis.vercel.app/api/ff-ban?uid={}",
        "param": "uid",
        "log": LOG_CHANNELS["ffban"],
        "extra_blacklist": []
    },
    "pincode": {
        "url": "https://api.postalpincode.in/pincode/{}",
        "param": "pincode",
        "log": LOG_CHANNELS["pincode"],
        "extra_blacklist": []
    },
    "ifsc": {
        "url": "https://abbas-apis.vercel.app/api/ifsc?ifsc={}",
        "param": "ifsc",
        "log": LOG_CHANNELS["ifsc"],
        "extra_blacklist": []
    },
    "gst": {
        "url": "https://api.b77bf911.workers.dev/gst?number={}",
        "param": "number",
        "log": LOG_CHANNELS["gst"],
        "extra_blacklist": []
    },
    "insta": {
        "url": "https://mkhossain.alwaysdata.net/instanum.php?username={}",
        "param": "username",
        "log": LOG_CHANNELS["insta"],
        "extra_blacklist": []
    },
    "tginfo": {
        "url": "https://openosintx.vippanel.in/tgusrinfo.php?key=OpenOSINTX-FREE&user={}",
        "param": "user",
        "log": LOG_CHANNELS["tginfo"],
        "extra_blacklist": []
    },
    "tginfopro": {
        "url": "https://api.b77bf911.workers.dev/telegram?user={}",
        "param": "user",
        "log": LOG_CHANNELS["tginfopro"],
        "extra_blacklist": []
    },
    "git": {
        "url": "https://abbas-apis.vercel.app/api/github?username={}",
        "param": "username",
        "log": LOG_CHANNELS["git"],
        "extra_blacklist": []
    },
    "pak": {
        "url": "https://abbas-apis.vercel.app/api/pakistan?number={}",
        "param": "number",
        "log": LOG_CHANNELS["pak"],
        "extra_blacklist": []
    },
}

# ==================== FOOTER & REDIRECT ====================
FOOTER = "\n\n<blockquote>developer: @Nullprotocol_X\npowered_by: NULL PROTOCOL</blockquote>"
REDIRECT_BOT = "@osintfatherNullBot"


