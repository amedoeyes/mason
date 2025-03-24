package cmd

import (
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"sort"
	"syscall"

	"github.com/amedoeyes/mason/pkg/context"
	"github.com/amedoeyes/mason/pkg/package"
	"github.com/amedoeyes/mason/pkg/receipt"
	"github.com/amedoeyes/mason/pkg/utility"
	"github.com/spf13/cobra"
)

var installCmd = &cobra.Command{
	Use:   "install [package...]",
	Short: "Install packages",
	Args:  cobra.MinimumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		ctx := cmd.Context().Value(contextKey).(*context.Context)

		lock, err := ctx.AcquireLock()
		if err != nil {
			panic(err)
		}
		defer func() {
			if err := lock.Unlock(); err != nil {
				panic(err)
			}
		}()

		removeDir := func(dir string) {
			if err := utility.SafeRemoveAll(dir, ctx.Config.DataDir); err != nil {
				panic(err)
			}
		}

		pkgsToInstall := make(map[*package_.Package]struct{}, len(args))

		for _, p := range args {
			if _, exists := ctx.Receipts[p]; exists {
				fmt.Printf("'%s' is already installed\n", p)
				return
			}

			pkg, exists := ctx.Packages[p]
			if !exists {
				fmt.Printf("'%s' does not exist\n", p)
				return
			}
			pkgsToInstall[pkg] = struct{}{}
		}

		pkgsSlice := make([]*package_.Package, 0, len(pkgsToInstall))
		for pkg := range pkgsToInstall {
			pkgsSlice = append(pkgsSlice, pkg)
		}

		sort.Slice(pkgsSlice, func(i, j int) bool {
			return pkgsSlice[i].Name < pkgsSlice[j].Name
		})

		maxTypeLen, maxNameLen, maxVerLen := 0, 0, 0
		for _, pkg := range pkgsSlice {
			maxTypeLen = max(maxTypeLen, len(pkg.Source.PURL.Type))
			maxNameLen = max(maxNameLen, len(pkg.Source.PURL.Name))
			maxVerLen = max(maxVerLen, len(pkg.Source.PURL.Version))
		}

		format := fmt.Sprintf("%%-%ds  %%-%ds  %%-%ds\n", maxTypeLen, maxNameLen, maxVerLen)
		for _, pkg := range pkgsSlice {
			fmt.Printf(format,
				pkg.Source.PURL.Type,
				pkg.Name,
				pkg.Source.PURL.Version,
			)
		}
		println()

		if !utility.ConfirmPrompt("Install?") {
			return
		}

		for _, pkg := range pkgsSlice {
			stgDir := filepath.Join(ctx.Config.StagingDir, pkg.Name)
			pkgDir := filepath.Join(ctx.Config.PackagesDir, pkg.Name)

			defer removeDir(stgDir)

			c := make(chan os.Signal, 1)
			if runtime.GOOS == "windows" {
				signal.Notify(c, os.Interrupt, syscall.Signal(0x1C))
			} else {
				signal.Notify(c, os.Interrupt, syscall.Signal(0xF), syscall.Signal(0x1))
			}
			go func() {
				<-c
				removeDir(stgDir)
				os.Exit(1)
			}()

			if err := os.MkdirAll(stgDir, 0755); err != nil {
				panic(err)
			}

			if err := pkg.Download(stgDir); err != nil {
				panic(err)
			}

			if err := pkg.Build(stgDir); err != nil {
				panic(err)
			}

			if err := os.Rename(stgDir, pkgDir); err != nil {
				panic(err)
			}

			if err := pkg.Link(pkgDir, ctx.Config.BinDir, ctx.Config.ShareDir, ctx.Config.OptDir); err != nil {
				pkg.Unlink(pkgDir, ctx.Config.BinDir, ctx.Config.ShareDir, ctx.Config.OptDir)
				removeDir(pkgDir)
				panic(err)
			}

			rct, err := receipt.FromPackage(pkg, pkgDir, ctx.Config.ShareDir, ctx.Config.OptDir)
			if err != nil {
				pkg.Unlink(pkgDir, ctx.Config.BinDir, ctx.Config.ShareDir, ctx.Config.OptDir)
				removeDir(pkgDir)
				panic(err)
			}

			if err := rct.Write(pkgDir); err != nil {
				pkg.Unlink(pkgDir, ctx.Config.BinDir, ctx.Config.ShareDir, ctx.Config.OptDir)
				removeDir(pkgDir)
				panic(err)
			}
		}
	},
}
