package package_

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
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
	Env *[]string
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
			case []any:
				var strSlice []string
				for _, val := range v {
					strSlice = append(strSlice, val.(string))
				}
				pkg.Source.Asset = &Asset{
					File: strSlice,
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
				env := []string{}
				for key, value := range envMap {
					if value, ok := value.(string); ok {
						env = append(env, fmt.Sprintf("%s=%s", key, value))
					}
				}
				pkg.Source.Build.Env = &env
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
		venvPython := utility.SelectByOS(
			filepath.Join("venv", "bin", "python"),
			filepath.Join("venv", "Scripts", "python.exe"),
		)

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

func (p *Package) Build(dir string) error {
	if p.Source.Build == nil {
		return nil
	}

	cmd := utility.SelectByOS(
		[]string{
			"bash",
			"-c",
			"set -euxo pipefail;\n" +
				p.Source.Build.Run,
		},
		[]string{
			"powershell",
			"-Command",
			"$ErrorActionPreference = 'Stop';" +
				"$ProgressPreference = 'SilentlyContinue';" +
				"[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12;" +
				p.Source.Build.Run,
		},
	)

	cmdExec := exec.Command(cmd[0], cmd[1:]...)
	if p.Source.Build.Env != nil {
		cmdExec.Env = append(os.Environ(), *p.Source.Build.Env...)
	}
	cmdExec.Dir = dir
	cmdExec.Stdout = os.Stdout
	cmdExec.Stderr = os.Stderr

	return cmdExec.Run()
}

func (p *Package) Link(dir, binDir, shareDir, optDir string) error {
	if p.Bin != nil {
		for dest, src := range p.ResolveBin() {
			if err := p.writeScript(dir); err != nil {
				return err
			}

			if err := os.Chmod(filepath.Join(dir, src), 0755); err != nil {
				return err
			}

			if err := utility.CreateSymlink(filepath.Join(dir, src), filepath.Join(binDir, dest)); err != nil {
				return err
			}
		}
	}

	if p.Share != nil {
		for dest, src := range *p.Share {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(shareDir, dest))
			if err != nil {
				return err
			}
			for dest, src := range res {
				if err := utility.CreateSymlink(src, dest); err != nil {
					return err
				}
			}
		}
	}

	if p.Opt != nil {
		for dest, src := range *p.Opt {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(optDir, dest))
			if err != nil {
				return err
			}
			for dest, src := range res {
				if err := utility.CreateSymlink(src, dest); err != nil {
					return err
				}
			}
		}
	}

	return nil
}

func (p *Package) Unlink(dir, binDir, shareDir, optDir string) error {
	if p.Bin != nil {
		for dest := range p.ResolveBin() {
			if err := utility.RemoveSymlink(filepath.Join(binDir, dest)); err != nil {
				return err
			}
		}
	}

	if p.Share != nil {
		for dest, src := range *p.Share {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(shareDir, dest))
			if err != nil {
				return err
			}
			for dest := range res {
				if err := utility.RemoveSymlink(dest); err != nil {
					return err
				}
			}
		}
	}

	if p.Opt != nil {
		for dest, src := range *p.Opt {
			res, err := utility.ResolveForSymLink(filepath.Join(dir, src), filepath.Join(optDir, dest))
			if err != nil {
				return err
			}
			for dest := range res {
				if err := utility.RemoveSymlink(dest); err != nil {
					return err
				}
			}
		}
	}

	return nil
}

func (p *Package) ResolveBin() map[string]string {
	result := map[string]string{}

	if p.Bin != nil {
		for dest, src := range *p.Bin {
			if strings.Contains(src, ":") {
				parts := strings.Split(src, ":")
				type_, target := parts[0], parts[1]

				switch type_ {
				case "dotnet", "exec", "gem", "java-jar", "node", "php", "python", "pyvenv", "ruby":
					src = utility.SelectByOS(dest, dest+".cmd")
				case "cargo":
					src = filepath.Join("bin", utility.SelectByOS(target, target+".exe"))
				case "composer":
					src = filepath.Join("vendor", "bin", utility.SelectByOS(target, target+".bat"))
				case "golang":
					src = utility.SelectByOS(target, target+".exe")
				case "luarocks":
					src = filepath.Join("bin", utility.SelectByOS(target, target+".bat"))
				case "npm":
					src = filepath.Join("node_modules", ".bin", utility.SelectByOS(target, target+".cmd"))
				case "nuget":
					src = utility.SelectByOS(target, target+".exe")
				case "opam":
					src = filepath.Join("bin", utility.SelectByOS(target, target+".exe"))
				case "pypi":
					src = filepath.Join("venv", utility.SelectByOS(filepath.Join("bin", target), filepath.Join("Scripts", target+".exe")))
				}
			}

			result[dest] = src
		}
	}

	return result
}

func (p *Package) writeScript(dir string) error {
	if p.Bin != nil {
		for dest, src := range *p.Bin {
			if strings.Contains(src, ":") {
				parts := strings.Split(src, ":")
				type_, target := parts[0], parts[1]

				src = filepath.Join(dir, utility.SelectByOS(dest, dest+".cmd"))
				var command string
				var env []string

				switch type_ {
				case "dotnet", "exec", "gem", "java-jar", "node", "php", "python", "pyvenv", "ruby":
					switch type_ {
					case "dotnet":
						command = fmt.Sprintf("dotnet \"%s\"", filepath.Join(dir, target))
					case "exec":
						command = filepath.Join(dir, target)
						if err := os.Chmod(command, 0755); err != nil {
							return err
						}
					case "gem":
						command = filepath.Join(dir, "bin", utility.SelectByOS(target, target+".bat"))
						env = []string{fmt.Sprintf("GEM_PATH=%s%s", dir, utility.SelectByOS(":$GEM_PATH", ";%%GEM_PATH%%"))}
					case "java-jar":
						command = fmt.Sprintf("java -jar \"%s\"", filepath.Join(dir, target))
					case "node":
						command = fmt.Sprintf("node \"%s\"", filepath.Join(dir, target))
					case "php":
						command = fmt.Sprintf("php \"%s\"", filepath.Join(dir, target))
					case "python":
						command = fmt.Sprintf("%s \"%s\"", utility.SelectByOS("python3", "python"), filepath.Join(dir, target))
					case "pyvenv":
						command = fmt.Sprintf("%s -m %s", utility.SelectByOS(filepath.Join("venv", "bin", "python"), filepath.Join("venv", "Scripts", "python.exe")), target)
					case "ruby":
						command = fmt.Sprintf("ruby \"%s\"", filepath.Join(dir, target))
					}

					if err := writeScript(src, command, env); err != nil {
						return err
					}
				}
			}
		}
	}

	return nil
}

var scriptTemplate = utility.SelectByOS(
	"#!/usr/bin/env bash\n%s\nexec %s \"$@\"\n",
	"@ECHO off\n%s\n%s %%*\n",
)

func writeScript(outPath, command string, env []string) error {
	envLines := []string{}
	for _, e := range env {
		envLines = append(envLines, fmt.Sprintf("%s %s", utility.SelectByOS("export", "SET"), e))
	}
	content := fmt.Sprintf(scriptTemplate, strings.Join(envLines, "\n"), command)
	return os.WriteFile(outPath, []byte(content), 0755)
}
