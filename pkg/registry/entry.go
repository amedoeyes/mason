package registry

import "github.com/package-url/packageurl-go"

type RegistryEntry struct {
	Name        string             `json:"name"`
	Description string             `json:"description"`
	Homepage    string             `json:"homepage"`
	Licenses    []string           `json:"licenses"`
	Languages   []string           `json:"languages"`
	Categories  []string           `json:"categories"`
	Deprecation *Deprecation       `json:"deprecation,omitempty"`
	Source      Source             `json:"source"`
	Bin         *map[string]string `json:"bin,omitempty"`
	Share       *map[string]string `json:"share,omitempty"`
	Opt         *map[string]string `json:"opt,omitempty"`
}

type Source struct {
	PURL             packageurl.PackageURL
	ID               string             `json:"id"`
	Asset            any                `json:"asset,omitempty"`    // can be an object or an array
	Build            any                `json:"build,omitempty"`    // can be an object or an array
	Download         any                `json:"download,omitempty"` // can be an object or an array
	Bin              *string            `json:"bin,omitempty"`
	ExtraPackages    *[]string          `json:"extra_packages,omitempty"`
	VersionOverrides *[]VersionOverride `json:"version_overrides,omitempty"`
}

type VersionOverride struct {
	Constraint string `json:"constraint"`
	ID         string `json:"id"`
	Asset      any    `json:"asset"`
}

type Build struct {
	Run string  `json:"run"`
	Env *string `json:"env,omitempty"`
}

type Deprecation struct {
	Message string `json:"message"`
	Since   string `json:"since"`
}
