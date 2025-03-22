package package_

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/amedoeyes/mason/pkg/registry"
	"github.com/amedoeyes/mason/pkg/utility"
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

func (p *Package) Download(dir string) error {
	run := func(cmd []string, env []string) error {
		if len(cmd) == 0 {
			return errors.New("empty command")
		}

		cmdExec := exec.Command(cmd[0], cmd[1:]...)
		cmdExec.Env = append(os.Environ(), env...)
		cmdExec.Dir = dir
		cmdExec.Stdout = os.Stdout
		cmdExec.Stderr = os.Stderr
		return cmdExec.Run()
	}

	type_ := p.Source.PURL.Type
	namespace := p.Source.PURL.Namespace
	name := p.Source.PURL.Name
	version := p.Source.PURL.Version
	qualifiers := p.Source.PURL.Qualifiers.Map()
	subpath := p.Source.PURL.Subpath

	switch type_ {
	case "cargo":
		cmd := []string{"cargo", "install", "--root", "."}
		if repoURL, exists := qualifiers["repository_url"]; exists {
			cmd = append(cmd, "--git", repoURL)
			if rev, exists := qualifiers["rev"]; exists && rev == "true" {
				cmd = append(cmd, "--rev", version)
			} else {
				cmd = append(cmd, "--tag", version)
			}
		} else {
			cmd = append(cmd, "--version", version)
		}
		if features, exists := qualifiers["features"]; exists {
			cmd = append(cmd, "--features", features)
		}
		if locked, exists := qualifiers["locked"]; exists && locked == "true" {
			cmd = append(cmd, "--locked")
		}
		cmd = append(cmd, name)

		if err := run(cmd, nil); err != nil {
			return err
		}

	case "composer":
		initCmd := []string{"composer", "init", "--no-interaction", "--stability=stable"}
		downCmd := []string{"composer", "require", fmt.Sprintf("%s/%s:%s", namespace, name, version)}

		if err := run(initCmd, nil); err != nil {
			return err
		}
		if err := run(downCmd, nil); err != nil {
			return err
		}

	case "gem":
		cmd := []string{"gem", "install", "--no-user-install", "--no-format-executable", "--install-dir=.", "--bindir=bin", "--no-document", fmt.Sprintf("%s:%s", name, version)}
		env := []string{fmt.Sprintf("GEM_HOME=%s", dir)}

		if err := run(cmd, env); err != nil {
			return err
		}

	case "generic":
		for outPath, url := range *p.Source.Download.Files {
			if err := utility.DownloadFile(url, outPath); err != nil {
				return err
			}
			if utility.IsExtractable(outPath) {
				if err := utility.ExtractFile(outPath, dir); err != nil {
					return err
				}
				os.Remove(outPath)
			}
		}

	case "github":
		repo := fmt.Sprintf("%s/%s", namespace, name)

		if p.Source.Asset != nil {
			for _, file := range p.Source.Asset.File {
				outDir := dir
				outPath := ""

				if strings.Contains(file, ":") {
					parts := strings.Split(file, ":")
					source := parts[0]
					dest := parts[1]

					if strings.HasSuffix(dest, "/") {
						outDir = filepath.Join(outDir, dest)
						outPath = filepath.Join(outDir, source)

						if err := os.MkdirAll(outDir, 0755); err != nil {
							return err
						}
						if err := utility.DownloadGithubRelease(repo, source, version, outDir); err != nil {
							return err
						}
					} else {
						outPath = filepath.Join(outDir, dest)

						if err := utility.DownloadGithubRelease(repo, source, version, outDir); err != nil {
							return err
						}
						if err := os.Rename(filepath.Join(outDir, source), outPath); err != nil {
							return err
						}
					}
				} else {
					outPath = filepath.Join(outDir, file)

					if err := utility.DownloadGithubRelease(repo, file, version, outDir); err != nil {
						return err
					}
				}

				if utility.IsExtractable(outPath) {
					if err := utility.ExtractFile(outPath, outDir); err != nil {
						return err
					}
					os.Remove(outPath)
				}
			}
		} else {
			cloneCmd := []string{"git", "clone", "--depth=1", fmt.Sprintf("https://github.com/%s.git", repo), dir}
			fetchCmd := []string{"git", "fetch", "--depth=1", "--tags", "origin", version}
			checkoutCmd := []string{"git", "checkout", version}

			if err := run(cloneCmd, nil); err != nil {
				return err
			}
			if err := run(fetchCmd, nil); err != nil {
				return err
			}
			if err := run(checkoutCmd, nil); err != nil {
				return err
			}
		}

	case "golang":
		target := fmt.Sprintf("%s/%s", namespace, name)
		if subpath != "" {
			target = fmt.Sprintf("%s/%s", target, subpath)
		}
		target = fmt.Sprintf("%s@%s", target, version)

		cmd := []string{"go", "install", "-v", target}
		env := []string{fmt.Sprintf("GOBIN=%s", dir)}

		if err := run(cmd, env); err != nil {
			return err
		}

	case "luarocks":
		cmd := []string{"luarocks", "install", "--tree", "."}
		if repoURL, ok := qualifiers["repository_url"]; ok {
			cmd = append(cmd, "--server", repoURL)
		}
		if dev, ok := qualifiers["dev"]; ok && dev == "true" {
			cmd = append(cmd, "--dev")
		}
		cmd = append(cmd, name, version)

		if err := run(cmd, nil); err != nil {
			return err
		}

	case "npm":
		target := name
		if namespace != "" {
			target = fmt.Sprintf("%s/%s", namespace, name)
		}
		target = fmt.Sprintf("%s@%s", target, version)

		initCmd := []string{"npm", "init", "--yes", "--scope=mason"}
		downCmd := []string{"npm", "install", target}
		if p.Source.ExtraPackages != nil {
			downCmd = append(downCmd, *p.Source.ExtraPackages...)
		}

		if err := os.WriteFile(filepath.Join(dir, ".npmrc"), []byte("install-strategy=shallow"), 0644); err != nil {
			return err
		}
		if err := run(initCmd, nil); err != nil {
			return err
		}
		if err := run(downCmd, nil); err != nil {
			return err
		}

	case "nuget":
		cmd := []string{"dotnet", "tool", "update", "--tool-path", ".", "--version", version, name}

		if err := run(cmd, nil); err != nil {
			return err
		}

	case "opam":
		cmd := []string{"opam", "install", "--destdir=.", "--yes", "--verbose", fmt.Sprintf("%s.%s", name, version)}

		if err := run(cmd, nil); err != nil {
			return err
		}

	case "openvsx":
		outPath := filepath.Join(dir, *p.Source.Download.File)
		url := fmt.Sprintf("https://open-vsx.org/api/%s/%s/%s/file/%s", namespace, name, version, *p.Source.Download.File)

		if err := utility.DownloadFile(url, outPath); err != nil {
			return err
		}
		if err := utility.ExtractFile(outPath, dir); err != nil {
			return err
		}
		os.Remove(outPath)

	case "pypi":
		python := utility.SelectByOS("python3", "python")
		venvPython := utility.SelectByOS(filepath.Join("venv", "bin", "python"), filepath.Join("venv", "Scripts", "python.exe"))

		initCmd := []string{python, "-m", "venv", "venv", "--system-site-packages"}
		extra := ""
		if ex, exists := qualifiers["extra"]; exists {
			extra = fmt.Sprintf("[%s]", ex)
		}
		downCmd := []string{venvPython, "-m", "pip", "--disable-pip-version-check", "install", "--ignore-installed", "-U", fmt.Sprintf("%s%s==%s", name, extra, version)}
		if p.Source.ExtraPackages != nil {
			downCmd = append(downCmd, *p.Source.ExtraPackages...)
		}

		if err := run(initCmd, nil); err != nil {
			return err
		}
		if err := run(downCmd, nil); err != nil {
			return err
		}

	default:
		return fmt.Errorf("packages of type '%s' are not implemented", type_)
	}

	return nil
}
