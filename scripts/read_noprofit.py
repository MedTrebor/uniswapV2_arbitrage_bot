import persistance
from rich import print


def main():
    noprofit_paths = persistance.load_noprofit_paths()

    tup_paths = list(noprofit_paths.items())
    list_paths = [list(path) for path in tup_paths]
    list_paths.sort(key=lambda x: x[1], reverse=True)

    noprofit_tokens = {}
    for path, count in list_paths:
        token_path = extract_tokens(path)
        if token_path in noprofit_paths:
            print(token_path)
            noprofit_tokens[token_path] += count
        else:
            noprofit_tokens[token_path] = count

    print(noprofit_tokens)


def extract_tokens(path: tuple[str, ...]) -> tuple[str, ...]:
    tokens = []
    for i in range(2, len(path) - 1, 2):
        tokens.append(path[i])

    return tuple(tokens)


if __name__ == "__main__":
    main()
