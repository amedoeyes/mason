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

func CreateSymlink(source, dest string) error {
	sourceInfo, err := os.Stat(source)
	if err != nil {
		return err
	}

	if sourceInfo.IsDir() {
		return filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if !info.IsDir() {
				relPath, err := filepath.Rel(source, path)
				if err != nil {
					return err
				}

				dest := filepath.Join(dest, relPath)

				if err := os.MkdirAll(filepath.Dir(dest), 0755); err != nil {
					return err
				}

				if err := os.Symlink(path, dest); err != nil {
					return err
				}
			}
			return nil
		})
	} else {
		return os.Symlink(source, dest)
	}
}

func RemoveSymlink(source, dest string) error {
	sourceInfo, err := os.Stat(source)
	if err != nil {
		return err
	}

	if sourceInfo.IsDir() {
		return filepath.Walk(source, func(path string, info os.FileInfo, err error) error {
			if err != nil {
				return err
			}

			if !info.IsDir() {
				relPath, err := filepath.Rel(source, path)
				if err != nil {
					return err
				}

				dest := filepath.Join(dest, relPath)

				destInfo, err := os.Stat(dest)
				if os.IsNotExist(err) {
					return nil
				}
				if err != nil {
					return err
				}

				if destInfo.Mode()&os.ModeSymlink != 0 {
					return os.Remove(dest)
				}
			}
			return nil
		})
	}

	destInfo, err := os.Stat(dest)
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
