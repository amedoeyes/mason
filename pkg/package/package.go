package package_

import (
	"github.com/amedoeyes/mason/pkg/registry"
	"github.com/package-url/packageurl-go"
)

type Package struct {
	Name        string
	Description string
	Homepage    string
	Licenses    []string
	Languages   []string
	Categories  []string
	Deprecation *Deprecation
	Source      Source
	Bin         *map[string]string
	Share       *map[string]string
	Opt         *map[string]string
}

type Source struct {
	PURL          packageurl.PackageURL
	Asset         *Asset
	Download      *Download
	Build         *Build
	ExtraPackages *[]string
}

type Deprecation struct {
	Message string
	Since   string
}

type Asset struct {
	File []string
}

type Download struct {
	File  *string
	Files *map[string]string
}

type Build struct {
	Run string
	Env *map[string]string
}

func NewPackage(entry registry.RegistryEntry) *Package {
	pkg := &Package{
		Name:        entry.Name,
		Description: entry.Description,
		Homepage:    entry.Homepage,
		Licenses:    entry.Licenses,
		Languages:   entry.Languages,
		Categories:  entry.Categories,
		Deprecation: (*Deprecation)(entry.Deprecation),
		Source: Source{
			PURL:          entry.Source.PURL,
			ExtraPackages: entry.Source.ExtraPackages,
		},
		Bin:   entry.Bin,
		Share: entry.Share,
		Opt:   entry.Opt,
	}

	if entry.Source.Asset != nil {
		if file, ok := entry.Source.Asset.(map[string]any)["file"]; ok {
			switch v := file.(type) {
			case string:
				pkg.Source.Asset = &Asset{
					File: []string{v},
				}
			case []string:
				pkg.Source.Asset = &Asset{
					File: v,
				}
			}
		}
	}

	if downloadMap, ok := entry.Source.Download.(map[string]any); ok {
		if filesRaw, exists := downloadMap["files"]; exists {
			if filesMap, ok := filesRaw.(map[string]any); ok {
				m := make(map[string]string, len(filesMap))
				for key, value := range filesMap {
					if value, ok := value.(string); ok {
						m[key] = value
					}
				}
				pkg.Source.Download = &Download{Files: &m}
			}
		}
		if fileRaw, exists := downloadMap["files"]; exists {
			if file, ok := fileRaw.(string); ok {
				pkg.Source.Download = &Download{File: &file}
			}
		}
	}

	if buildMap, ok := entry.Source.Build.(map[string]any); ok {
		if runRaw, exists := buildMap["run"]; exists {
			if run, ok := runRaw.(string); ok {
				pkg.Source.Build = &Build{Run: run}
			}
		}
		if envRaw, exists := buildMap["env"]; exists {
			if envMap, ok := envRaw.(map[string]any); ok {
				m := make(map[string]string, len(envMap))
				for key, value := range envMap {
					if value, ok := value.(string); ok {
						m[key] = value
					}
				}
				pkg.Source.Build.Env = &m
			}
		}
	}

	return pkg
}
