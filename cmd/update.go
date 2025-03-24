package cmd

import (
	"github.com/amedoeyes/mason/pkg/context"
	"github.com/spf13/cobra"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update repositories",
	Run: func(cmd *cobra.Command, args []string) {
		ctx := cmd.Context().Value(contextKey).(*context.Context)

		for _, reg := range ctx.Registries {
			if err := reg.Update(); err != nil {
				panic(err)
			}
		}
	},
}
