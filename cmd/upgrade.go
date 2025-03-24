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

var upgradeCmd = &cobra.Command{
	Use:   "upgrade [package...]",
	Short: "Upgrade packages",
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

		pkgsToUpgrade := make(map[*package_.Package]*receipt.Receipt, len(ctx.Receipts))

		if len(args) == 0 {
			for _, rct := range ctx.Receipts {
				pkg, exists := ctx.Packages[rct.Name]
				if !exists {
					continue
				}

				if pkg.Source.PURL.Version != rct.PrimarySource.PURL.Version {
					pkgsToUpgrade[pkg] = rct
				}
			}
		} else {
			for _, p := range args {
				pkg, exists := ctx.Packages[p]
				if !exists {
					fmt.Printf("'%s' does not exist\n", p)
					return
				}

				rct, exists := ctx.Receipts[p]
				if !exists {
					fmt.Printf("'%s' is not installed\n", p)
					return
				}

				if pkg.Source.PURL.Version != rct.PrimarySource.PURL.Version {
					pkgsToUpgrade[pkg] = rct
				}
			}
		}

		pkgsSlice := make([]*package_.Package, 0, len(pkgsToUpgrade))
		for pkg := range pkgsToUpgrade {
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

		if len(pkgsToUpgrade) == 0 {
			return
		}

		format := fmt.Sprintf("%%-%ds %%-%ds %%-%ds -> %%s\n", maxTypeLen, maxNameLen, maxVerLen)
		for _, pkg := range pkgsSlice {
			rct := pkgsToUpgrade[pkg]
			fmt.Printf(format,
				rct.PrimarySource.PURL.Type,
				rct.Name,
				rct.PrimarySource.PURL.Version,
				pkg.Source.PURL.Version,
			)
		}
		println()

		if !utility.ConfirmPrompt("Upgrade?") {
			return
		}

		for _, pkg := range pkgsSlice {
			rct := pkgsToUpgrade[pkg]
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

			for dest := range rct.Links.Bin {
				if err := os.Remove(filepath.Join(ctx.Config.BinDir, dest)); err != nil {
					panic(err)
				}
			}

			for dest := range rct.Links.Share {
				if err := os.Remove(filepath.Join(ctx.Config.ShareDir, dest)); err != nil {
					panic(err)
				}
			}

			for dest := range rct.Links.Opt {
				if err := os.Remove(filepath.Join(ctx.Config.OptDir, dest)); err != nil {
					panic(err)
				}
			}

			removeDir(pkgDir)

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
