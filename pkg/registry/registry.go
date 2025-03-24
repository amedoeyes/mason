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
	"github.com/package-url/packageurl-go"
	"gopkg.in/yaml.v3"
)

type Registry struct {
	kind   string
	source string
	dir    string
	info   RegistryInfo
}

type RegistryInfo struct {
	DownloadTimestamp int64             `json:"download_timestamp"`
	Version           string            `json:"version"`
	Checksums         map[string]string `json:"checksums"`
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

		regExists, err := utility.PathExists(registryFile)
		if err != nil {
			return nil, err
		}
		infoExists, err := utility.PathExists(infoFile)
		if err != nil {
			return nil, err
		}
		if !regExists || !infoExists {
			if err := utility.DownloadGithubRelease(source, "registry.json.zip", "", dir); err != nil {
				return nil, err
			}

			if err := utility.DownloadGithubRelease(source, "checksums.txt", "", dir); err != nil {
				return nil, err
			}

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

			os.Remove(registryZipFile)
			os.Remove(checksumsFile)

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

func (r *Registry) Load() ([]RegistryEntry, error) {
	var entries []RegistryEntry

	switch r.kind {
	case "github":
		data, err := os.ReadFile(filepath.Join(r.dir, "registry.json"))
		if err != nil {
			return nil, err
		}

		err = json.Unmarshal(data, &entries)
		if err != nil {
			return nil, err
		}

	case "file":
		dirs, err := os.ReadDir(filepath.Join(r.source, "packages"))
		if err != nil {
			return nil, err
		}

		for _, dir := range dirs {
			data, err := os.ReadFile(filepath.Join(r.source, "packages", dir.Name(), "package.yaml"))
			if err != nil {
				return nil, err
			}

			var entry RegistryEntry
			err = yaml.Unmarshal(data, &entry)
			if err != nil {
				return nil, err
			}

			entries = append(entries, entry)
		}

	default:
		return nil, fmt.Errorf("registry kind '%s' not implemented", r.kind)
	}

	for i := range entries {
		entries[i].Description = strings.ReplaceAll(entries[i].Description, "\n", " ")

		switch v := entries[i].Source.Asset.(type) {
		case []any:
			for _, item := range v {
				switch v := item.(map[string]any)["target"].(type) {
				case string:
					if utility.IsPlatform(v) {
						entries[i].Source.Asset = item
						break
					}
				case []any:
					var strSlice []string
					for _, val := range v {
						strSlice = append(strSlice, val.(string))
					}
					if utility.IsPlatform(strSlice...) {
						entries[i].Source.Asset = item
						break
					}
				}
			}
		}

		switch v := entries[i].Source.Build.(type) {
		case []any:
			for _, item := range v {
				switch v := item.(map[string]any)["target"].(type) {
				case string:
					if utility.IsPlatform(v) {
						entries[i].Source.Build = item
						break
					}
				case []any:
					var strSlice []string
					for _, val := range v {
						strSlice = append(strSlice, val.(string))
					}
					if utility.IsPlatform(strSlice...) {
						entries[i].Source.Build = item
						break
					}
				}
			}
		}

		switch v := entries[i].Source.Download.(type) {
		case []any:
			for _, item := range v {
				switch v := item.(map[string]any)["target"].(type) {
				case string:
					if utility.IsPlatform(v) {
						entries[i].Source.Download = item
						break
					}
				case []any:
					var strSlice []string
					for _, val := range v {
						strSlice = append(strSlice, val.(string))
					}
					if utility.IsPlatform(strSlice...) {
						entries[i].Source.Download = item
						break
					}
				}
			}
		}

		var err error
		entries[i].Source.PURL, err = packageurl.FromString(entries[i].Source.ID)
		if err != nil {
			return nil, err
		}

		prev := ""
		entryStr, err := json.Marshal(entries[i])
		if err != nil {
			return nil, err
		}

		var ctx map[string]any
		if err := json.Unmarshal(entryStr, &ctx); err != nil {
			return nil, err
		}
		ctx["version"] = entries[i].Source.PURL.Version

		for prev != string(entryStr) {
			prev = string(entryStr)
			res, err := renderTemplate(string(entryStr), ctx)
			if err != nil {
				return nil, err
			}
			entryStr = []byte(res)
		}

		if err := json.Unmarshal(entryStr, &entries[i]); err != nil {
			return nil, err
		}
	}

	return entries, nil
}
