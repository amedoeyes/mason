package cmd

import (
	"fmt"
	"sort"

	"github.com/amedoeyes/mason/pkg/context"
	"github.com/amedoeyes/mason/pkg/receipt"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List installed packages",
	Run: func(cmd *cobra.Command, args []string) {
		ctx := cmd.Context().Value(contextKey).(*context.Context)

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
	},
}
