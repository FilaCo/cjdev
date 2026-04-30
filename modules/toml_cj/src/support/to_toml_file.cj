protected package toml_cj.support

public interface ToTOMLFile {
    func toTOMLFile(): TOMLFile
}

public func toTOMLFile<T>(toml: T): TOMLFile where T <: ToTOMLFile {
    toml.toTOMLFile()
}
