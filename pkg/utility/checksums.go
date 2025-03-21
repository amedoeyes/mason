package utility

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
)

func ReadChecksums(checksumsFile string) (map[string]string, error) {
	data, err := os.ReadFile(checksumsFile)
	if err != nil {
		return nil, err
	}
	checksums := make(map[string]string)
	for line := range strings.SplitSeq(string(data), "\n") {
		if line == "" {
			continue
		}
		fields := strings.Fields(line)
		if len(fields) != 2 {
			continue
		}
		checksums[fields[1]] = fields[0]
	}
	return checksums, nil
}

func VerifyChecksums(checksums map[string]string, dir string) (bool, error) {
	for filename, checksum := range checksums {
		fileBytes, err := os.ReadFile(filepath.Join(dir, filename))
		if err != nil {
			return false, err
		}
		hash := sha256.Sum256(fileBytes)
		if hex.EncodeToString(hash[:]) != checksum {
			return false, nil
		}
	}
	return true, nil
}
