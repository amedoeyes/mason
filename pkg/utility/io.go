package utility

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func PathExists(path string) bool {
	_, err := os.Stat(path)
	return !os.IsNotExist(err)
}

func SafeRemoveAll(dir, base string) error {
	absDir, err := filepath.Abs(dir)
	if err != nil {
		return fmt.Errorf("could not resolve %s: %w", dir, err)
	}

	absBase, err := filepath.Abs(base)
	if err != nil {
		return fmt.Errorf("could not resolve base %s: %w", base, err)
	}

	if !strings.HasPrefix(absDir, absBase) {
		return fmt.Errorf("directory %s is outside the trusted base %s", absDir, absBase)
	}

	info, err := os.Lstat(absDir)
	if err != nil {
		return fmt.Errorf("failed to stat %s: %w", absDir, err)
	}

	if !info.IsDir() && info.Mode()&os.ModeSymlink == 0 {
		return fmt.Errorf("%s is not a valid directory", absDir)
	}

	return os.RemoveAll(absDir)
}
