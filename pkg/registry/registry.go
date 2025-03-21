package registry

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/amedoeyes/mason/pkg/utility"
	"gopkg.in/yaml.v3"
)

type RegistryInfo struct {
	DownloadTimestamp int64             `json:"download_timestamp"`
	Version           string            `json:"version"`
	Checksums         map[string]string `json:"checksums"`
}

type Registry struct {
	kind   string
	source string
	dir    string
	info   RegistryInfo
}

func NewRegistry(registry, dir string) (*Registry, error) {
	kind, source, found := strings.Cut(registry, ":")
	var info RegistryInfo
	if !found {
		return nil, fmt.Errorf("invalid registry format: '%s'", registry)
	}
	switch kind {
	case "github":
		dir = filepath.Join(dir, "github", source)
		registryZipFile := filepath.Join(dir, "registry.json.zip")
		registryFile := filepath.Join(dir, "registry.json")
		checksumsFile := filepath.Join(dir, "checksums.txt")
		infoFile := filepath.Join(dir, "info.json")

		if !utility.FileExists(registryFile) || !utility.FileExists(infoFile) {
			if err := utility.DownloadGithubRelease(source, "registry.json.zip", "", dir); err != nil {
				return nil, err
			}

			if err := utility.DownloadGithubRelease(source, "checksums.txt", "", dir); err != nil {
				return nil, err
			}

			os.Remove(registryZipFile)
			os.Remove(checksumsFile)

			utility.ExtractFile(registryZipFile, dir)

			checksums, err := utility.ReadChecksums(checksumsFile)
			if err != nil {
				return nil, err
			}
			if ok, err := utility.VerifyChecksums(checksums, dir); !ok {
				if err != nil {
					return nil, err
				}
				return nil, fmt.Errorf("checksums missmatch for '%s'", source)
			}

			resp, err := http.Get(fmt.Sprintf("https://api.github.com/repos/%s/releases/latest", source))
			if err != nil {
				return nil, err
			}
			defer resp.Body.Close()

			var data map[string]any
			err = json.NewDecoder(resp.Body).Decode(&data)
			if err != nil {
				return nil, err
			}

			info = RegistryInfo{
				DownloadTimestamp: time.Now().Unix(),
				Version:           data["tag_name"].(string),
				Checksums:         checksums,
			}

			jsonData, err := json.Marshal(info)
			if err != nil {
				return nil, err
			}

			if err = os.WriteFile(infoFile, jsonData, 0644); err != nil {
				return nil, err
			}
		} else {
			data, err := os.ReadFile(infoFile)
			if err != nil {
				return nil, err
			}

			err = json.Unmarshal(data, &info)
			if err != nil {
				return nil, err
			}
		}
	case "file":

	default:
		return nil, fmt.Errorf("invalid registry kind: '%s'", kind)
	}

	return &Registry{kind: kind, source: source, dir: dir, info: info}, nil
}

func (r *Registry) Update() error {
	switch r.kind {
	case "github":
		resp, err := http.Get(fmt.Sprintf("https://api.github.com/repos/%s/releases/latest", r.source))
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		var data map[string]any
		if err = json.NewDecoder(resp.Body).Decode(&data); err != nil {
			return err
		}

		if data["tag_name"].(string) != r.info.Version {
			registryZipFile := filepath.Join(r.dir, "registry.json.zip")
			checksumsFile := filepath.Join(r.dir, "checksums.txt")
			infoFile := filepath.Join(r.dir, "info.json")

			if err := utility.DownloadGithubRelease(r.source, "registry.json.zip", "", r.dir); err != nil {
				return err
			}

			if err := utility.DownloadGithubRelease(r.source, "checksums.txt", "", r.dir); err != nil {
				return err
			}

			utility.ExtractFile(registryZipFile, r.dir)

			checksums, err := utility.ReadChecksums(checksumsFile)
			if err != nil {
				return err
			}
			if ok, err := utility.VerifyChecksums(checksums, r.dir); !ok {
				if err != nil {
					return err
				}
				return fmt.Errorf("checksums missmatch for '%s'", r.source)
			}

			os.Remove(registryZipFile)
			os.Remove(checksumsFile)

			r.info = RegistryInfo{
				DownloadTimestamp: time.Now().Unix(),
				Version:           data["tag_name"].(string),
				Checksums:         checksums,
			}

			jsonData, err := json.Marshal(r.info)
			if err != nil {
				return err
			}

			if err = os.WriteFile(infoFile, jsonData, 0644); err != nil {
				return err
			}
		}
	case "file":

	default:
		return fmt.Errorf("registry type '%s' not implemented", r.kind)
	}

	return nil
}

func (r *Registry) Load() ([]map[string]any, error) {
	var packages []map[string]any

	switch r.kind {
	case "github":
		data, err := os.ReadFile(filepath.Join(r.dir, "registry.json"))
		if err != nil {
			return nil, err
		}

		err = json.Unmarshal(data, &packages)
		if err != nil {
			return nil, err
		}

	case "file":
		entries, err := os.ReadDir(filepath.Join(r.source, "packages"))
		if err != nil {
			return nil, err
		}

		for _, entry := range entries {
			data, err := os.ReadFile(filepath.Join(r.source, "packages", entry.Name(), "package.yaml"))
			if err != nil {
				return nil, err
			}

			var pkg map[string]any
			err = yaml.Unmarshal(data, &pkg)
			if err != nil {
				return nil, err
			}

			packages = append(packages, pkg)
		}

	default:
		return nil, fmt.Errorf("registry kind '%s' not implemented", r.kind)
	}

	return packages, nil
}
