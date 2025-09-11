from src.pipeline import main

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool_usage", default=False, required=False)
    args = parser.parse_args()
    if args.tool_usage:
        main(tool_usage=True)
    else:
        main()
