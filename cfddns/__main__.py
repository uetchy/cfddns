if __name__ == "__main__":
    from .cli import main

    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)