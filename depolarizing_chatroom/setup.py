import asyncio

from .data.crud import build_prod_database

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild of production database",
    )
    args = parser.parse_args()

    asyncio.run(build_prod_database(args.force))
