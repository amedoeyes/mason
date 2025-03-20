package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
)

var (
	category string
	language string
)

var searchCmd = &cobra.Command{
	Use:   "search [query]",
	Short: "Search packages",
	Args:  cobra.MaximumNArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		query := ""
		if len(args) > 0 {
			query = args[0]
		}
		fmt.Printf("Search command called with query: '%s', category: '%s', language: '%s'\n", query, category, language)
	},
}

func init() {
	searchCmd.Flags().StringVarP(&category, "category", "c", "", "Specify category of package (dap, formatter, linter, lsp)")
	searchCmd.Flags().StringVarP(&language, "language", "l", "", "Specify language of package")
}
