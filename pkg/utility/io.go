package utility

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func PathExists(path string) (bool, error) {
	if _, err := os.Lstat(path); err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	return true, nil
}

func ResolveForSymLink(src, dest string) (map[string]string, error) {
	result := make(map[string]string)

	sourceInfo, err := os.Stat(src)
	if err != nil {
		return nil, err
	}

	if sourceInfo.IsDir() {
		filepath.Walk(src, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if !info.IsDir() {
				relPath, err := filepath.Rel(src, path)
				if err != nil {
					return err
				}

				result[filepath.Join(dest, relPath)] = path
			}
			return nil
		})
	} else {
		result[dest] = src
	}

	return result, nil
}

func CreateSymlink(src, dest string) error {
	if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
		return err
	}
	if err := os.Symlink(src, dest); err != nil {
		return err
	}
	return nil
}

func RemoveSymlink(dest string) error {
	destInfo, err := os.Lstat(dest)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if destInfo.Mode()&os.ModeSymlink != 0 {
		return os.Remove(dest)
	}
	return nil
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
