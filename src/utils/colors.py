class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'

    # Foreground
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'

    # Background
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'

    @staticmethod
    def colored(text, color):
        return f"{color}{text}{Colors.RESET}"

    @staticmethod
    def success(text):
        return f"{Colors.GREEN}✅ {text}{Colors.RESET}"

    @staticmethod
    def error(text):
        return f"{Colors.RED}❌ {text}{Colors.RESET}"

    @staticmethod
    def warning(text):
        return f"{Colors.YELLOW}⚠️  {text}{Colors.RESET}"

    @staticmethod
    def info_text(text):
        return f"{Colors.CYAN}ℹ️  {text}{Colors.RESET}"
