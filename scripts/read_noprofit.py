import persistance
from rich import print


def main():
    noprofit_paths = persistance.load_noprofit_paths()

    tup_paths = list(noprofit_paths.items())
    list_paths = [list(path) for path in tup_paths]
    list_paths.sort(key=lambda x: x[1], reverse=True)

    noprofit_tokens = {}
    for path, count in list_paths:
        tokens = extract_tokens(path)
        for token in tokens:
            if token in noprofit_tokens:
                noprofit_tokens[token] += count
            else:
                noprofit_tokens[token] = count

    print(noprofit_tokens)


def extract_tokens(path: tuple[str, ...]) -> list[str]:
    tokens = []
    for i in range(2, len(path) - 1, 2):
        tokens.append(path[i])

    return tokens


if __name__ == "__main__":
    main()
