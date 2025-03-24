package cmd

import (
	"fmt"
	"os"
	"path/filepath"

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

		receits := make(map[*receipt.Receipt]struct{}, len(args))

		for _, p := range args {
			rct, exists := ctx.Receipts[p]
			if !exists {
				fmt.Printf("'%s' is not installed\n", p)
				return
			}
			receits[rct] = struct{}{}
		}

		maxTypeLen, maxNameLen, maxVerLen := 0, 0, 0
		for rct := range receits {
			if len(rct.PrimarySource.PURL.Type) > maxTypeLen {
				maxTypeLen = len(rct.PrimarySource.PURL.Type)
			}
			if len(rct.Name) > maxNameLen {
				maxNameLen = len(rct.Name)
			}
			if len(rct.PrimarySource.PURL.Version) > maxVerLen {
				maxVerLen = len(rct.PrimarySource.PURL.Version)
			}
		}

		format := fmt.Sprintf("%%-%ds %%-%ds %%-%ds\n", maxTypeLen, maxNameLen, maxVerLen)
		for rct := range receits {
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

		for rct := range receits {
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
