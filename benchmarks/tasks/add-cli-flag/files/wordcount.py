import argparse
from collections import Counter


def count_words(text):
    return Counter(text.lower().split())


def main(argv=None):
    parser = argparse.ArgumentParser(description="Count words in a file.")
    parser.add_argument("path")
    args = parser.parse_args(argv)
    with open(args.path, encoding="utf-8") as f:
        counts = count_words(f.read())
    for word, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"{word} {n}")


if __name__ == "__main__":
    main()
