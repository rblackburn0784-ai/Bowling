"""Static Discord UI contract tests, safe to run without discord.py installed."""
import ast
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]

class MenuContractTests(unittest.TestCase):
    def _classes(self,path):
        return {n.name:n for n in ast.parse((ROOT/path).read_text()).body if isinstance(n,ast.ClassDef)}
    def test_new_public_records_are_not_admin_gated(self):
        menu=self._classes('cogs/menu.py')
        self.assertIn('PublicMenu',menu)
        board=self._classes('cogs/dashboard_ui.py')['CareerRecordView']
        self.assertEqual(ast.unparse(board.bases[0]), 'discord.ui.View')
        names=[x.name for x in board.body if isinstance(x,ast.AsyncFunctionDef)]
        self.assertIn('home',names)
        self.assertNotIn('interaction_check',names)
    def test_button_rows_fit_discord_limits(self):
        for path in ('cogs/menu.py','cogs/dashboard_ui.py','cogs/director.py'):
            for cls in self._classes(path).values():
                buttons=[]
                for node in cls.body:
                    if not isinstance(node,ast.AsyncFunctionDef):continue
                    for deco in node.decorator_list:
                        if isinstance(deco,ast.Call) and isinstance(deco.func,ast.Attribute) and deco.func.attr=='button':
                            row=next((x.value.value for x in deco.keywords if x.arg=='row' and isinstance(x.value,ast.Constant)),None)
                            if row is not None:self.assertIn(row,range(5),f'{path}:{cls.name}')
                            buttons.append(row)
                self.assertLessEqual(len(buttons),25,f'{path}:{cls.name}')
                for r in range(5):self.assertLessEqual(buttons.count(r),5,f'{path}:{cls.name} row {r}')
    def test_admin_awards_and_tournaments_have_runtime_checks(self):
        a=self._classes('cogs/awards.py')['Awards'];t=self._classes('cogs/tournaments.py')['Tournaments']
        self.assertIn('cog_app_command_check',[n.name for n in t.body if isinstance(n,ast.AsyncFunctionDef)])
        give=next(n for n in a.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='give')
        self.assertIn('admin_ok',ast.unparse(give))
if __name__=='__main__':unittest.main()
