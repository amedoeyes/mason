package context

import (
	"context"

	"github.com/amedoeyes/mason/config"
	"github.com/amedoeyes/mason/pkg/registry"
)

type Context struct {
	context.Context
	Config     *config.Config
	Registries []*registry.Registry
}

func NewContext(ctx context.Context) (*Context, error) {
	new_ctx := &Context{
		Context: ctx,
		Config:  config.NewConfig(),
	}
	new_ctx.Registries = make([]*registry.Registry, 0, len(new_ctx.Config.Registries))

	for _, r := range new_ctx.Config.Registries {
		reg, err := registry.NewRegistry(r, new_ctx.Config.RegistriesDir)
		if err != nil {
			return nil, err
		}
		new_ctx.Registries = append(new_ctx.Registries, reg)
	}

	return new_ctx, nil
}
