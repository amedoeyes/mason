package registry

import (
	"errors"
	"fmt"
	"regexp"
	"strings"

	"github.com/amedoeyes/mason/pkg/utility"
)

func renderTemplate(template string, context map[string]any) (string, error) {
	re := regexp.MustCompile(`{{\s*(.*?)\s*}}`)
	var outErr error
	result := re.ReplaceAllStringFunc(template, func(match string) string {
		value, err := evalTemplate(re.FindStringSubmatch(match)[1], context)
		if err != nil {
			outErr = err
			return ""
		}
		return fmt.Sprintf("%v", value)
	})
	if outErr != nil {
		return "", outErr
	}

	return result, nil
}

var filters = map[string]func(value, arg any) (any, error){
	"equals": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("equals requires argument")
		}
		return value == arg, nil
	},

	"not_equals": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("no_equals requires an argument")
		}
		return value != arg, nil
	},

	"strip_prefix": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("strip_prefix requires an argument")
		}
		str, ok := value.(string)
		if !ok {
			return nil, errors.New("value must be a string")
		}
		prefix, ok := arg.(string)
		if !ok {
			return nil, errors.New("prefix must be a string")
		}
		if strings.HasPrefix(str, prefix) {
			return str[len(prefix):], nil
		}
		return str, nil
	},

	"strip_suffix": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("strip_suffix requires an argument")
		}
		str, ok := value.(string)
		if !ok {
			return nil, errors.New("str must be a string")
		}
		suffix, ok := arg.(string)
		if !ok {
			return nil, errors.New("suffix must be a string")
		}
		if strings.HasSuffix(str, suffix) {
			return str[:len(str)-len(suffix)], nil
		}
		return str, nil
	},

	"take_if": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("take_if requires an argument")
		}
		cond, ok := arg.(bool)
		if !ok {
			return nil, errors.New("condition must be a boolean")
		}
		if cond {
			return value, nil
		}
		return "", nil
	},

	"take_if_not": func(value, arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("take_if_not requires an argument")
		}
		cond, ok := arg.(bool)
		if !ok {
			return nil, errors.New("condition must be a boolean")
		}
		if !cond {
			return value, nil
		}
		return "", nil
	},

	"to_lower": func(value, _ any) (any, error) {
		str, ok := value.(string)
		if !ok {
			return nil, errors.New("value must be a string")
		}
		return strings.ToLower(str), nil
	},

	"to_upper": func(value, _ any) (any, error) {
		str, ok := value.(string)
		if !ok {
			return nil, errors.New("value must be a string")
		}
		return strings.ToUpper(str), nil
	},
}

var functions = map[string]func(args any) (any, error){
	"is_platform": func(arg any) (any, error) {
		if arg == nil {
			return nil, errors.New("is_platform requires an argument")
		}
		plat, ok := arg.(string)
		if !ok {
			return nil, errors.New("plat must be a string")
		}
		return utility.IsPlatform(plat), nil
	},
}

func evalTemplate(template string, context map[string]any) (any, error) {
	parts := strings.Split(template, "|")
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}

	value, err := evalValue(parts[0], context)
	if err != nil {
		return nil, err
	}

	for _, filter := range parts[1:] {
		if len(filter) == 0 {
			continue
		}

		var filtName string
		var arg any

		if strings.Contains(filter, "(") && strings.HasSuffix(filter, ")") {
			openIdx := strings.Index(filter, "(")
			closeIdx := strings.LastIndex(filter, ")")
			if openIdx == -1 || closeIdx == -1 || closeIdx < openIdx {
				return nil, fmt.Errorf("invalid filter syntax: %s", filter)
			}

			filtName = strings.TrimSpace(filter[:openIdx])
			argStr := filter[openIdx+1 : closeIdx]
			arg, err = evalArg(argStr, context)
			if err != nil {
				return nil, err
			}
		} else {
			parts := strings.Split(filter, " ")
			for i := range parts {
				parts[i] = strings.TrimSpace(parts[i])
			}

			filtName = parts[0]
			if len(parts) > 1 {
				str, err := parseString(parts[1])
				if err != nil {
					return nil, err
				}
				arg = str
			}
		}

		filterFunc, ok := filters[filtName]
		if !ok {
			return nil, fmt.Errorf("unknown filter: %s", filtName)
		}

		value, err = filterFunc(value, arg)
		if err != nil {
			return nil, err
		}
	}

	return value, nil
}

func evalValue(expr string, context map[string]any) (any, error) {
	str, err := parseString(expr)
	if err == nil {
		return str, nil
	}

	parts := strings.Split(expr, ".")
	for i := range parts {
		parts[i] = strings.TrimSpace(parts[i])
	}

	value, ok := context[parts[0]]
	if !ok {
		return nil, fmt.Errorf("variable %s not found", parts[0])
	}

	for _, part := range parts[1:] {
		if m, ok := value.(map[string]any); ok {
			value = m[part]
		} else {
			value = nil
		}
		if value == nil {
			return nil, fmt.Errorf("cannot resolve attribute/key %s", part)
		}
	}

	return value, nil
}

func evalArg(argStr string, context map[string]any) (any, error) {
	if strings.TrimSpace(argStr) == "" {
		return "", nil
	}

	var arg any

	if strings.Contains(argStr, "(") && strings.HasSuffix(argStr, ")") {
		openIdx := strings.Index(argStr, "(")
		closeIdx := strings.LastIndex(argStr, ")")
		if openIdx == -1 || closeIdx == -1 || closeIdx < openIdx {
			return nil, fmt.Errorf("invalid function syntax in argument: %s", argStr)
		}

		funcName := strings.TrimSpace(argStr[:openIdx])
		innerArgStr := argStr[openIdx+1 : closeIdx]
		funcArg, err := evalArg(innerArgStr, context)
		if err != nil {
			return nil, err
		}

		funcFunc, ok := functions[funcName]
		if !ok {
			return nil, fmt.Errorf("unknown function: %s", funcName)
		}

		arg, err = funcFunc(funcArg)
		if err != nil {
			return nil, err
		}
	} else {
		str, err := parseString(argStr)
		if err == nil {
			arg = str
		} else {
			if val, ok := context[argStr]; ok {
				arg = val
			} else {
				arg = argStr
			}
		}
	}

	return arg, nil
}

func parseString(s string) (any, error) {
	s = strings.TrimSpace(s)
	if (strings.HasPrefix(s, "\"") && strings.HasSuffix(s, "\"")) ||
		(strings.HasPrefix(s, "'") && strings.HasSuffix(s, "'")) {
		return s[1 : len(s)-1], nil
	}
	return nil, fmt.Errorf("not a string: %s", s)
}
