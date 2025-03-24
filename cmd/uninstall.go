package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/amedoeyes/mason/pkg/context"
	"github.com/amedoeyes/mason/pkg/receipt"
	"github.com/amedoeyes/mason/pkg/utility"
	"github.com/spf13/cobra"
)

var uninstallCmd = &cobra.Command{
	Use:   "uninstall [package...]",
	Short: "Uninstall packages",
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

		receits := make(map[*receipt.Receipt]struct{}, len(args))

		for _, p := range args {
			rct, exists := ctx.Receipts[p]
			if !exists {
				fmt.Printf("'%s' is not installed\n", p)
				return
			}
			receits[rct] = struct{}{}
		}

		receiptsSlice := make([]*receipt.Receipt, 0, len(ctx.Receipts))
		for _, rct := range ctx.Receipts {
			receiptsSlice = append(receiptsSlice, rct)
		}

		sort.Slice(receiptsSlice, func(i, j int) bool {
			return receiptsSlice[i].Name < receiptsSlice[j].Name
		})

		maxTypeLen, maxNameLen, maxVerLen := 0, 0, 0
		for _, rct := range receiptsSlice {
			maxTypeLen = max(maxTypeLen, len(rct.PrimarySource.PURL.Type))
			maxNameLen = max(maxNameLen, len(rct.PrimarySource.PURL.Name))
			maxVerLen = max(maxVerLen, len(rct.PrimarySource.PURL.Version))
		}

		format := fmt.Sprintf("%%-%ds  %%-%ds  %%-%ds\n", maxTypeLen, maxNameLen, maxVerLen)
		for _, rct := range receiptsSlice {
			fmt.Printf(format,
				rct.PrimarySource.PURL.Type,
				rct.Name,
				rct.PrimarySource.PURL.Version,
			)
		}
		println()

		if !utility.ConfirmPrompt("Uninstall?") {
			return
		}

		for _, rct := range receiptsSlice {
			pkgDir := filepath.Join(ctx.Config.PackagesDir, rct.Name)

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

			if err := utility.SafeRemoveAll(pkgDir, ctx.Config.DataDir); err != nil {
				panic(err)
			}
		}
	},
}
