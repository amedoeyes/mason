package context

import (
	"github.com/amedoeyes/mason/config"
	package_ "github.com/amedoeyes/mason/pkg/package"
	"github.com/amedoeyes/mason/pkg/registry"
)

type Context struct {
	Config     *config.Config
	Registries []*registry.Registry
	Packages   map[string]*package_.Package
}

func NewContext() (*Context, error) {
	new_ctx := &Context{
		Config: config.NewConfig(),
	}
	new_ctx.Registries = make([]*registry.Registry, 0, len(new_ctx.Config.Registries))

	for _, r := range new_ctx.Config.Registries {
		reg, err := registry.NewRegistry(r, new_ctx.Config.RegistriesDir)
		if err != nil {
			return nil, err
		}
		new_ctx.Registries = append(new_ctx.Registries, reg)
	}

	new_ctx.Packages = map[string]*package_.Package{}
	for _, r := range new_ctx.Registries {
		entries, err := r.Load()
		if err != nil {
			return nil, err
		}
		for _, e := range entries {
			new_ctx.Packages[e.Name] = package_.NewPackage(e)
		}
	}

	return new_ctx, nil
}
