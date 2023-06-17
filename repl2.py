class ResultException(SystemExit):
    val: any
    def __init__(self, val):
        self.val = val
        super().__init__()

def respond(val):
    raise ResultException(val)


import sys

# `with buffered_repl_interaction():` wraps displayhook and sys.stdout/stderr
# it's a context manager that returns a function that can be used to
class buffered_repl_interaction(object):
    def __init__(self, ctx):
        self.ctx = ctx
        ctx["respond"] = respond

    def __enter__(self):
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        self._displayhook = sys.displayhook
        if "__r_value_count" not in self.ctx:
            self.ctx["__r_value_count"] = 0

        if "Out" not in self.ctx:
            self.ctx["Out"] = {}

        def displayhook(value):
            val_name = self.ctx["__r_value_count"]
            self.ctx["__r_value_count"] += 1

            # self.ctx[val_name] = value
            self.ctx["Out"][val_name] = value
            if value is not None:
                # print(f"=== {val_name} ===")
                print(f"Out[{val_name}]: ", end="")
            self._displayhook(value)
        sys.displayhook = displayhook

        # swizzle sys.stdout and sys.stderr to an io.StringIO (https://docs.python.org/3/library/io.html)
        # so we capture stdout/stderr writes regardless of where the write comes from- ie. a print() inside some inner function
        import io
        self.stdout_buffer = sys.stdout = sys.stderr = io.StringIO()

        # track which globals are new or changed
        self.pre_ctx = self.ctx.copy()

        return self

    def __exit__(self, *exc_info):
        excluded_globals = {'__r_value_count'}
        for k, v in self.ctx.items():
            if k not in self.pre_ctx or v != self.pre_ctx[k] and k not in excluded_globals:
                print(f"{k}: {repr(v)}")
        self.pre_ctx = None

        sys.stdout = self._stdout
        sys.stderr = self._stderr
        sys.displayhook = self._displayhook

    def get_output(self):
        return self.stdout_buffer.getvalue()

def interactive_shell(ctx):
    """
    Strategy:
    - swizzle sys.displayhook(value) to get output like `[v12]: value`.
      See https://docs.python.org/3/library/sys.html#sys.displayhook
    - swizzle sys.stdout and sys.stderr to an io.StringIO (https://docs.python.org/3/library/io.html)
      so we caputre stdout/stderr writes regardless of where the write comes from- ie. a print() inside some inner function

    Note we should then be able to replace our copied `repl.py` with the builtin `code`
    module as in the flask shell. We'd need to either pass in readfunc or replace sys.stdin with
    a StringIO. We'd probably want to interact with the InteractiveInterpreter directly in either
    case, because we want to know if the code is malformed.
    """

    ### Copied from `flask shell`

    # Site, customize, or startup script can set a hook to call when
    # entering interactive mode. The default one sets up readline with
    # tab and history completion.
    interactive_hook = getattr(sys, "__interactivehook__", None)

    if interactive_hook is not None:
        try:
            import readline
            from rlcompleter import Completer
        except ImportError:
            pass
        else:
            # rlcompleter uses __main__.__dict__ by default, which is
            # flask.__main__. Use the shell context instead.
            readline.set_completer(Completer(ctx).complete)

        interactive_hook()

    from code import InteractiveConsole

    # copied from code.py's interact() fn. I'm not sure what it does
    try:
        import readline
    except ImportError:
        pass

    try:
        console = InteractiveConsole(ctx)

        # swizzle console.runsource(self, source, filename, symbol) to wrap in buffered_repl_interaction
        old_runsource = console.runsource
        def runsource(source, *args, **kwargs):
            interceptor = buffered_repl_interaction(ctx)
            with interceptor:
                ret = old_runsource(source, *args, **kwargs)
            print(interceptor.get_output())
            return ret
        console.runsource = runsource

        console.interact(banner="", exitmsg="")

    except ResultException as res:
        return res.val


class UnforgivingRepl(object):
    def __init__(self, ctx):
        from code import InteractiveInterpreter
        self.ctx = ctx
        self.console = InteractiveInterpreter(ctx)
        self.result = None

    def __call__(self, source):
        interceptor = buffered_repl_interaction(self.ctx)

        try:
            with interceptor:
                # add extra "\n\n" to source so if we could keep going, we don't have to
                more = self.console.runsource(source + "\n", "<console>", symbol="single")
                if more:
                    print("SyntaxError: unexpected EOF while parsing")

        except ResultException as res:
            self.result = res.val


        return interceptor.get_output()

class UnforgivingRepl2(object):
    def __init__(self, ctx):
        from code import InteractiveConsole
        self.ctx = ctx
        self.console = InteractiveConsole(locals=ctx, filename="<console>")
        self.result = None

    def __call__(self, source):
        interceptor = buffered_repl_interaction(self.ctx)

        try:
            with interceptor:
                # add extra "\n\n" to source so if we could keep going, we don't have to
                for line in source.splitlines():
                    more = self.console.push(line)

                if more:
                    more = self.console.push("\n")
                    more = self.console.push("\n")

                if more:
                    print("SyntaxError: unexpected EOF while parsing")

        except ResultException as res:
            self.result = res.val


        return interceptor.get_output()



