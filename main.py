import sys
from coordinator import KeystrokeCoordinator

def main():
    manager = KeystrokeCoordinator()

    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "collect":
            manager.collect_data()
        elif command == "verify":
            manager.verify_user()
        elif command == "reset":
            manager.reset_database()
        else:
            print("Usage: python main.py [collect|verify|reset]")
    else:
        print("Usage: python main.py [collect|verify|reset]")

if __name__ == "__main__":
    main()