# Tema Visual GEUNID-JASEB
# Blue, White, Fancy, Elegant, & Professional

UI_COLORS = {
    'primary': '#007AFF',      # Sapphire Blue (iOS Style)
    'secondary': '#FFFFFF',    # Frost White
    'background': '#F2F2F7',   # Light Grayish Blue (Premium Look)
    'text_primary': '#000000', # Deep Black
    'accent': '#5856D6'        # Royal Purple Accent
}

EMOJI_UI = {
    'start': '💎',
    'package': '📦',
    'order': '💳',
    'profile': '👤',
    'logs': '📜',
    'success': '🔹',
    'failed': '🔸',
    'loading': '⌛',
    'warning': '⚠️',
    'money': '💰',
    'back': '⬅️',
    'forward': '🔵',
    'rocket': '🚀',
    'shield': '🛡️',
    'analytics': '📊'
}

def format_menu_text(title, content):
    """Format teks menu agar rapi dan mewah sesuai standar GeunID (Blue & White)"""
    divider = "━━━━━━━━━━━━━━━━━━━━"
    return f"**{title}**\n{divider}\n\n{content}\n\n{divider}"
