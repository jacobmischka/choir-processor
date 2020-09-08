#!/usr/bin/env python3

from argparse import ArgumentParser
from os.path import splitext, join
from xml.etree import ElementTree as ET
import sys, os


def parse_file(path):
    try:
        _, ext = splitext(path)
        if ext == ".java":
            return JavaQuestionnaire(path)
        elif ext == ".xml":
            return XmlQuestionnaire(path)
    except Exception as e:
        print("Failed parsing file {}, {}".format(path, e))


def print_file(path):
    print(parse_file(path))


def main():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title="commands")
    subparsers.add_parser("process").set_defaults(func=handle_process)
    subparsers.add_parser("questionnaire").set_defaults(func=handle_questionnaire)
    subparsers.add_parser("dir").set_defaults(func=handle_questionnaire_dir)
    parser.add_argument("infile")
    parser.add_argument("-o, --outfile", required=False, dest="outfile")

    args = parser.parse_args()

    result = args.func(args)

    if args.func != handle_questionnaire_dir:
        if args.outfile:
            with open(args.outfile, "w") as outfile:
                print(result, file=outfile)
        else:
            print(result)


def handle_process(args):
    process = Process(args.infile)
    return process.get_process_type(input("Enter a process type: "))


def handle_questionnaire(args):
    return parse_file(args.infile)


def handle_questionnaire_dir(args):
    if not args.outfile:
        print("Must specify an out directory when using dir", file=sys.stderr)
        return

    os.makedirs(args.outfile, exist_ok=True)

    for root, dirs, files in os.walk(args.infile):
        for file_name in files:
            basename, ext = splitext(file_name)
            out_name = "{}.md".format(basename)
            out_path = join(args.outfile, out_name)

            in_path = join(root, file_name)
            with open(out_path, "w") as outfile:
                print(parse_file(in_path), file=outfile)


class Process(object):
    def __init__(self, path):
        self.tree = ET.parse(path)
        self.root = self.tree.getroot()

    def get_process_type(self, value):
        for process_type in self.root:
            if process_type.attrib["value"] == value:
                return ProcessType(value, process_type)


class ProcessType(object):
    def __init__(self, title, root):
        self.title = title
        self.root = root
        self.questionnaires = [
            self.parse_questionnaire(x) for x in self.root.iter("Questionaire")
        ]

    @staticmethod
    def parse_questionnaire(q_root):
        try:
            q_type = q_root.attrib["type"]
            if q_type == "Local":
                path = q_root.attrib["xml"] + ".xml"
                return XmlQuestionnaire(path)
            else:
                print("Unknown Questionnaire type: {}".format(q_type), file=sys.stderr)
                return Questionnaire(q_root.attrib["value"])
        except Exception:
            return None

    def __str__(self):
        s = ""

        s += "# {}\n\n".format(self.title)

        s += "\n".join([str(q) for q in self.questionnaires])

        return s


class Questionnaire(object):
    def __init__(self, title=None):
        self.title = title
        self.questions = []

    def add_question(self, question):
        self.questions.append(question)

    def __str__(self):
        s = ""

        if self.title:
            s += "## {}\n\n".format(self.title)

        s += "\n".join(set([str(q) for q in self.questions]))

        return s


class XmlQuestionnaire(Questionnaire):
    def __init__(self, path):
        tree = ET.parse(path)
        form = tree.getroot()

        super().__init__(form.attrib.get("Description"))

        items = form.find("Items")
        if items:
            for item in items.iter("Item"):
                descriptions = item.findall("Description")
                title = None
                subtitle = None
                if len(descriptions) > 0:
                    title = descriptions[0].text
                if len(descriptions) > 1:
                    subtitle = descriptions[1].text
                question = Question(title, subtitle)

                responses = item.find("Responses").findall("Response")
                if responses:
                    for response in responses:
                        response_type = response.get("Type")
                        if response_type == "select1" or response_type == "select":
                            for i in response.iter("item"):
                                label = i.find("label").text
                                value = i.find("value").text
                                question.add_option(label, value)
                        elif response_type == "radio":
                            value = ""
                            score = response.find("Score")
                            if score:
                                value = score.get("value")
                            question.add_option(response.get("Description"), value)
                        elif response_type == "input":
                            pass
                        else:
                            print(
                                "ERROR: Unsupported response type: {}".format(
                                    response.get("Type")
                                ),
                                file=sys.stderr,
                            )

                self.add_question(question)


class JavaQuestionnaire(Questionnaire):
    def __init__(self, path):
        super().__init__()

        items = self.get_items(path)
        for item in items:
            self.add_question(self.parse_item(item))

    @staticmethod
    def get_items(path):
        items = []

        current_item = None
        with open(path, "r") as infile:
            for line in infile:
                if line.strip().startswith("item("):
                    current_item = line
                elif line.strip() == ")," or line.strip() == ")":
                    current_item += line
                    items.append(current_item)
                    current_item = None
                elif current_item is not None:
                    current_item += line

        return items

    @staticmethod
    def parse_item(item):
        question = None
        for line in item.split("\n"):
            line = line.strip()

            if line.startswith("item("):
                pieces = line.split(",")
                title = pieces[1].strip().replace('"', "")
                subtitle = pieces[2].strip().replace('"', "")
                question = Question(title, subtitle)
            elif line.startswith("response("):
                line = line.replace("response(", "").replace(")", "")
                [text, val, *_] = line.split(",")
                question.add_option(text.strip().replace('"', ""), val.strip())

        return question


class Question(object):
    def __init__(self, title, subtitle=None):
        if title and isinstance(title, str):
            title = title.strip()
        self.title = title
        self.subtitle = subtitle
        self.options = []

    def add_option(self, text, value):
        self.options.append((text, value))

    def __repr__(self):
        s = "Question({}, {}, [".format(self.title, self.subtitle)
        for (text, value) in self.options:
            s += "\n\t({}, {}),\n".format(text, value)
        s += "])"
        return s

    def __str__(self):
        s = ""
        if self.title:
            s += "\n### {}\n\n".format(self.title)
        if self.subtitle:
            s += "\n#### {}\n\n".format(self.subtitle)

        for i, (text, _) in enumerate(self.options):
            s += "{}. {}\n".format(i + 1, text)

        return s


if __name__ == "__main__":
    main()
