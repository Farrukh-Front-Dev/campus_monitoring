#!/usr/bin/env python3
"""
School21 Advanced Analytics Tool (Entry Point)
Imports CLI and display logic from src package and runs.
"""

import sys
from src.config import load_cli_config, CLI_CONFIG
from src.utils.colors import Colors
from src.analytics import APIClient, Analytics, Menu, run_all, Exporter, Display

def main():
    load_cli_config()

    args = sys.argv[1:]
    interactive_mode = '--interactive' in args or '-i' in args
    
    Display.banner()

    print(f"  {Colors.YELLOW}🔐 Autentifikatsiya...{Colors.RESET}")
    client = APIClient()
    client.authenticate()
    print(f"  {Colors.success('Token olindi!')}")

    analytics = Analytics(client)

    if interactive_mode:
        while True:
            Menu.show()
            choice = Menu.get_choice()

            if choice == 'q':
                print(f"\n  {Colors.success('Ko`rishguncha! 👋')}\n")
                break
            elif choice == 'a':
                run_all(analytics)
            elif choice == 'e':
                if analytics.collected_data:
                    Exporter.to_json(analytics.collected_data)
                else:
                    print(Colors.warning("Avval ma'lumot yig'ing (a tanlang)"))
            elif choice == 't':
                if analytics.collected_data:
                    Exporter.to_txt(analytics.collected_data)
                else:
                    print(Colors.warning("Avval ma'lumot yig'ing (a tanlang)"))
            else:
                found = False
                for num, name, method_name in Menu.SECTIONS:
                    if choice == num:
                        method = getattr(analytics, method_name, None)
                        if method:
                            try:
                                method()
                            except Exception as e:
                                print(Colors.error(f"Xatolik: {e}"))
                        found = True
                        break
                if not found:
                    print(Colors.warning("Noto'g'ri tanlov!"))
    else:
        run_all(analytics)

        if '--export-json' in args:
            Exporter.to_json(analytics.collected_data)
        if '--export-txt' in args:
            Exporter.to_txt(analytics.collected_data)

    print(f"\n{'━' * 60}")
    print(f"  {Colors.BOLD}📊 Session statistikasi:{Colors.RESET}")
    Display.kv("API so'rovlar", client.stats['requests'])
    Display.kv("Keshdan", client.stats['cached'])
    Display.kv("Xatoliklar", client.stats['errors'],
               Colors.RED if client.stats['errors'] > 0 else Colors.GREEN)
    Display.kv("Bo'limlar", len(analytics.collected_data))
    print(f"{'━' * 60}\n")

if __name__ == "__main__":
    main()
