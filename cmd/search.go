package cmd

import (
	"fmt"
	"sort"
	"strings"

	"github.com/amedoeyes/mason/pkg/context"
	"github.com/amedoeyes/mason/pkg/package"
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
		ctx := cmd.Context().Value(contextKey).(*context.Context)

		query := ""
		if len(args) > 0 {
			query = args[0]
		}

		pkgsSlice := make([]*package_.Package, 0, len(ctx.Packages))
		for _, pkg := range ctx.Packages {
			pkgsSlice = append(pkgsSlice, pkg)
		}

		sort.Slice(pkgsSlice, func(i, j int) bool {
			return pkgsSlice[i].Name < pkgsSlice[j].Name
		})

		for _, pkg := range pkgsSlice {
			if !match(pkg, query) {
				continue
			}

			fmt.Printf("%s  %s\n", pkg.Name, pkg.Source.PURL.Version)
			if pkg.Deprecation != nil {
				fmt.Printf("    Deprecation: %s\n", pkg.Deprecation.Message)
			}
			fmt.Printf("    Description: %s\n", pkg.Description)
			fmt.Printf("    Homepage: %s\n", pkg.Homepage)
			fmt.Printf("    Categories: %s\n", strings.Join(pkg.Categories, ", "))
			if len(pkg.Languages) > 0 {
				fmt.Printf("    Languages: %s\n", strings.Join(pkg.Languages, ", "))
			}
			fmt.Printf("    Licenses: %s\n\n", strings.Join(pkg.Licenses, ", "))
		}
	},
}

func match(pkg *package_.Package, query string) bool {
	if category != "" {
		found := false
		for _, c := range pkg.Categories {
			if strings.EqualFold(category, c) {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	if language != "" {
		found := false
		for _, l := range pkg.Languages {
			if strings.EqualFold(language, l) {
				found = true
				break
			}
		}
		if !found {
			return false
		}
	}

	query = strings.ToLower(query)
	return strings.Contains(strings.ToLower(pkg.Name), query) || strings.Contains(strings.ToLower(pkg.Description), query)
}

func init() {
	searchCmd.Flags().StringVarP(&category, "category", "c", "", "Specify category of package (dap, formatter, linter, lsp)")
	searchCmd.Flags().StringVarP(&language, "language", "l", "", "Specify language of package")
}
