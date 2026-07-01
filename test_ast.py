import ast

class CallbackVisitor(ast.NodeVisitor):
    def __init__(self):
        self.conditions = []
    
    def visit_If(self, node):
        self.conditions.append(ast.unparse(node.test))
        for item in node.orelse:
            if isinstance(item, ast.If):
                self.visit_If(item)
        self.generic_visit(node)

with open('handlers/callback_handler.py', 'r', encoding='utf-8') as f:
    tree = ast.parse(f.read())
    visitor = CallbackVisitor()
    visitor.visit(tree)

data = 'prompt_s20_8_risk_pct'
for cond in visitor.conditions:
    try:
        # evaluate the condition safely
        res = eval(cond, {'data': data, 'config': None, 'active_strategies': {}})
        if res:
            print(f"Matched condition: {cond}")
            break
    except Exception as e:
        pass
