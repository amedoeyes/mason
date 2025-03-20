package config

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/amedoeyes/mason/pkg/utility"
)

type Config struct {
	DataDir       string
	RegistriesDir string
	PackagesDir   string
	BinDir        string
	ShareDir      string
	OptDir        string
	RegistryRepo  string
	RegistryPath  string
	Registries    []string
}

func getEnv(key, fallback string) string {
	if value, ok := os.LookupEnv(key); ok {
		return value
	}
	return fallback
}

func NewConfig() *Config {
	config := &Config{}

	home, err := os.UserHomeDir()
	if err != nil {
		panic("cannot determine user home directory: " + err.Error())
	}

	config.DataDir = os.Getenv("MASON_DATA_DIR")
	if config.DataDir == "" {
		config.DataDir = filepath.Join(utility.SelectByOS(
			getEnv("XDG_DATA_HOME", filepath.Join(home, ".local", "share")),
			getEnv("APPDATA", filepath.Join(home, "AppData", "Roaming")),
		), "mason")
	}

	config.RegistriesDir = filepath.Join(config.DataDir, "registries")
	config.PackagesDir = filepath.Join(config.DataDir, "packages")
	config.BinDir = filepath.Join(config.DataDir, "bin")
	config.ShareDir = filepath.Join(config.DataDir, "share")
	config.OptDir = filepath.Join(config.DataDir, "opt")

	var registries []string
	regs := getEnv("MASON_REGISTRIES", "github:mason-org/mason-registry")
	for r := range strings.SplitSeq(regs, ",") {
		if trimmed := strings.TrimSpace(r); trimmed != "" {
			registries = append(registries, trimmed)
		}
	}

	return config
}
