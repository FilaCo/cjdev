package cjdev.third_party.cli

protected class Parser {
    public Parser(private let _input: Array<String>, private let _spec: Command) {
    }

    public func parse(): ArgumentMatches {
        for (arg in _input) {
            if (arg.startsWith("--")) {
            }
        }
    }
}
