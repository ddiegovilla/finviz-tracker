from src.startup import startup_message

startup_message("Importing desktop application")
from src.desktop import main


if __name__ == "__main__":
    startup_message("Starting desktop application")
    main()
    startup_message("Desktop application returned normally")
