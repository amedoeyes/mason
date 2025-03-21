package utility

import (
	"archive/tar"
	"archive/zip"
	"compress/bzip2"
	"compress/gzip"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/ulikunitz/xz"
)

func ExtractFile(filePath, outDir string) error {
	lowerName := strings.ToLower(filePath)
	switch {
	case strings.HasSuffix(lowerName, ".gz"):
		return decompressGzip(filePath, outDir)
	case strings.HasSuffix(lowerName, ".tar"):
		return extractTar(filePath, outDir)
	case strings.HasSuffix(lowerName, ".tar.bz2") || strings.HasSuffix(lowerName, ".tbz2"):
		return extractTarBz2(filePath, outDir)
	case strings.HasSuffix(lowerName, ".tar.gz") || strings.HasSuffix(lowerName, ".tgz"):
		return extractTarGz(filePath, outDir)
	case strings.HasSuffix(lowerName, ".tar.xz") || strings.HasSuffix(lowerName, ".txz"):
		return extractTarXz(filePath, outDir)
	case strings.HasSuffix(lowerName, ".zip") || strings.HasSuffix(lowerName, ".vsix"):
		return extractZip(filePath, outDir)
	default:
		return fmt.Errorf("unsupported file type: %s", filePath)
	}
}

func IsExtractable(filePath string) bool {
	lowerName := strings.ToLower(filePath)
	return strings.HasSuffix(lowerName, ".gz") ||
		strings.HasSuffix(lowerName, ".tar") ||
		strings.HasSuffix(lowerName, ".tar.bz2") ||
		strings.HasSuffix(lowerName, ".tar.xz") ||
		strings.HasSuffix(lowerName, ".tbz2") ||
		strings.HasSuffix(lowerName, ".tgz") ||
		strings.HasSuffix(lowerName, ".txz") ||
		strings.HasSuffix(lowerName, ".vsix") ||
		strings.HasSuffix(lowerName, ".zip")
}

func decompressGzip(filePath, outDir string) error {
	f, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer f.Close()
	gzr, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gzr.Close()
	outFilePath := filepath.Join(outDir, strings.TrimSuffix(filepath.Base(filePath), ".gz"))
	outFile, err := os.Create(outFilePath)
	if err != nil {
		return err
	}
	defer outFile.Close()
	_, err = io.Copy(outFile, gzr)
	return err
}

func extractTar(filePath, outDir string) error {
	f, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer f.Close()
	return extractTarFromReader(f, outDir)
}

func extractTarBz2(filePath, outDir string) error {
	f, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer f.Close()
	bz2r := bzip2.NewReader(f)
	return extractTarFromReader(bz2r, outDir)
}

func extractTarGz(filePath, outDir string) error {
	f, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer f.Close()
	gzr, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gzr.Close()
	return extractTarFromReader(gzr, outDir)
}

func extractTarXz(filePath, outDir string) error {
	f, err := os.Open(filePath)
	if err != nil {
		return err
	}
	defer f.Close()
	xzr, err := xz.NewReader(f)
	if err != nil {
		return err
	}
	return extractTarFromReader(xzr, outDir)
}

func extractTarFromReader(r io.Reader, outDir string) error {
	tarReader := tar.NewReader(r)
	for {
		header, err := tarReader.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return err
		}
		target := filepath.Join(outDir, header.Name)
		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return err
			}
			outFile, err := os.Create(target)
			if err != nil {
				return err
			}
			if _, err := io.Copy(outFile, tarReader); err != nil {
				outFile.Close()
				return err
			}
			outFile.Close()
		default:
		}
	}
	return nil
}

func extractZip(filePath, outDir string) error {
	r, err := zip.OpenReader(filePath)
	if err != nil {
		return err
	}
	defer r.Close()
	for _, f := range r.File {
		fpath := filepath.Join(outDir, f.Name)
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(fpath, f.Mode()); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(fpath), 0755); err != nil {
			return err
		}
		outFile, err := os.OpenFile(fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
		if err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			outFile.Close()
			return err
		}
		_, err = io.Copy(outFile, rc)
		outFile.Close()
		rc.Close()
		if err != nil {
			return err
		}
	}
	return nil
}
