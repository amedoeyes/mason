package utility

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"github.com/schollz/progressbar/v3"
)

func DownloadFile(url, outPath string) error {
	resp, err := http.Get(url)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("failed to download: status %s", resp.Status)
	}
	totalSize := resp.ContentLength
	outFile, err := os.Create(outPath)
	if err != nil {
		return err
	}
	defer outFile.Close()
	bar := progressbar.DefaultBytes(totalSize, fmt.Sprintf("downloading '%s'", filepath.Base(outFile.Name())))
	_, err = io.Copy(io.MultiWriter(outFile, bar), resp.Body)
	return err
}

func DownloadGithubRelease(repo, asset, version, outDir string) error {
	var url string
	if version != "" {
		url = fmt.Sprintf("https://github.com/%s/releases/download/%s/%s", repo, version, asset)
	} else {
		url = fmt.Sprintf("https://github.com/%s/releases/latest/download/%s", repo, asset)
	}
	return DownloadFile(url, filepath.Join(outDir, asset))
}
