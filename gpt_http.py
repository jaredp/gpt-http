import flask
from flask import render_template_string, request
import sys
import time
import flask_login
from yachalk import chalk


class Conversation(object):
    def __init__(self, system):
        self.convo = ""
        self.append(system, "system")

    def append(self, text, speaker):
        self.convo += text

        # print to console
        color = lambda text: text
        if speaker == "system":
            color = chalk.blue
        elif speaker == "gpt":
            color = chalk.red
        elif speaker == "python":
            color = chalk.green
        print(color(text), end="")

    def toStr(self):
        return self.convo


import re
import openai

openai.api_key = open("openai-api-key.txt").read().strip()


def _gpt_completion(convo, stop_words):
    completions = openai.Completion.create(
        engine="text-davinci-003",
        prompt=convo,
        max_tokens=1000,
        n=1,
        stop=stop_words,
        temperature=0,
    )
    return completions.choices[0].text


def gpt_completion(convo, stop_words):
    tries = 0
    while tries < 5:
        try:
            return _gpt_completion(convo, stop_words)
        except openai.error.RateLimitError:
            time.sleep(2**tries * 0.25)
            tries += 1


def gpt_agent(prelude, prerecording):
    if len(prerecording) > 0:
        # pop from the start of the list
        gpt_response = prerecording.pop(0)
    else:
        gpt_response = gpt_completion(
            prelude, stop_words=["\n```endpython", "\n```endjinja"]
        )

    parts = re.split(r"\n```(python|jinja)\n", gpt_response)
    if len(parts) != 3:
        raise ValueError("GPT responded in unknown format, got %s" % gpt_response)
    [thought, tool, code] = parts
    gpt_response += "\n```end%s\n" % tool

    return (gpt_response, tool, code)


def suggest_inspect(model_name, attr_name):
    return f""" I should avoid features that need {model_name}.{attr_name} since it doesn't exist. What information does the database have about this {model_name}?
```python
print(inspect.getsource({model_name}))"""


import argparse

parser = argparse.ArgumentParser(description="Have GPT hallucinate a web app")
parser.add_argument(
    "--shell",
    action="store_true",
    help="Start an interactive repl for each request, like flask shell, where the user can live respond to a request",
)
parser.add_argument(
    "--confirm",
    action="store_true",
    help="Wait for the user to accept each GPT suggestion before proceeding",
)
parser.add_argument(
    "--prerecording",
    type=str,
    metavar="FILENAME",
    help="Use a prerecorded conversation from a file",
)
parser.add_argument(
    "--debug-prerecording",
    action="store_true",
    help="Drop into a repl when the prerecording is done, to allow for debugging",
)
args = parser.parse_args()

from repl2 import interactive_shell, UnforgivingRepl, UnforgivingRepl2


def gpt_hallucinate(app, get_gbls):
    @app.route("/", defaults={"path": ""}, methods=["GET", "POST"])
    @app.route("/<path:path>", methods=["GET", "POST"])
    def catch_all(path):
        # set up the globals that will be accessible in the shell
        ctx = {}
        ctx.update(get_gbls())
        ctx.update({"all_variables": ctx})
        ctx.update({k: getattr(flask, k) for k in dir(flask)})
        ctx.update({k: getattr(flask_login, k) for k in dir(flask_login)})
        ctx.update(app.make_shell_context())

        # in interactive testing mode, just start a shell
        if args.shell:
            return interactive_shell(ctx)

        # get the prompt and first few expected responses
        prerecord_file = (
            "view-prompt.txt" if request.method == "GET" else "mutate-prompt.txt"
        )
        if args.prerecording:
            prerecord_file = args.prerecording
        prerecording = open(prerecord_file).read().split("\n\n==AUTORESPOND==\n\n")

        # track the conversation
        convo = Conversation(prerecording.pop(0))

        # start a long-running shell with the globals
        repl = UnforgivingRepl2(ctx)

        while True:
            running_prerecording = len(prerecording) > 0

            # if we're out of prerecorded responses, start an interactive shell
            if args.debug_prerecording and running_prerecording:
                return interactive_shell(ctx)

            # prompt for thought
            convo.append("\nThought:", "system")

            # ask gpt
            (gpt_response, tool, code) = gpt_agent(convo.toStr(), prerecording)
            convo.append(gpt_response, "gpt")

            if args.confirm and not running_prerecording:
                input("Press enter to continue")

            # keep track of some pre state
            previous_exception = sys.last_value if hasattr(sys, "last_value") else None
            ex = None

            # run the code
            try:
                if tool == "python":
                    python_result = repl(code)
                    if repl.result != None:
                        return repl.result

                elif tool == "jinja":
                    return render_template_string(code, **ctx)
                else:
                    python_result = f"GPT responded with unknown tool {tool}"
            except Exception as e:
                # only for jinja errors— python errors are handled by the repl
                ex = e
                python_result = "Error: " + str(e)
                if not python_result.endswith("\n"):
                    python_result += "\n"
            if hasattr(sys, "last_value") and sys.last_value != previous_exception:
                ex = sys.last_value

            convo.append(python_result, "python")

            def suggest(suggested_response):
                prerecording.insert(0, suggested_response)

            if (
                ex
                and isinstance(ex, AttributeError)
                and isinstance(ex.obj, PrintableMixin)
                and ctx[ex.obj.__class__.__name__] == ex.obj.__class__
            ):
                suggest(suggest_inspect(ex.obj.__class__.__name__, ex.name))

            elif ex and isinstance(ex, jinja2.UndefinedError):
                # use regex to pull `Product` and `foo` out of a string like `'__main__.Product object' has no attribute 'foo'`
                match = re.search(
                    r"'__main__\.(\w+) object' has no attribute '(\w+)'",
                    str(ex.message),
                )
                model_name = match.group(1) if match else None
                attribute_name = match.group(2) if match else None
                if (
                    model_name
                    and attribute_name
                    and (model_name in ctx and ctx[model_name].__name__ == model_name)
                ):
                    suggest(suggest_inspect(model_name, attribute_name))

    ## Customize flask to our needs

    import jinja2
    from jinja2 import StrictUndefined

    app.jinja_env.undefined = StrictUndefined

    # disable url_for. If anyone calls url_for, it will raise an exception telling them to
    # hardcode the url instead
    def url_for(*args, **kwargs):
        raise Exception("url_for() is not allowed. Hardcode the url instead.")

    flask.url_for = url_for
    flask.helpers.url_for = url_for
