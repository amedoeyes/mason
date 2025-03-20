package context

import (
	"context"

	"github.com/amedoeyes/mason/config"
)

type Context struct {
	context.Context
	Config *config.Config
}

func NewContext(ctx context.Context) *Context {
	return &Context{
		Context: ctx,
		Config:  config.NewConfig(),
	}
}
