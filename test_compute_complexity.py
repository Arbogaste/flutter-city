from compute_complexity import complexity_of_source


def test_straight_line_method_is_zero():
    src = b'''
    class Foo {
      void m() { print(1); print(2); }
    }
    '''
    assert complexity_of_source(src) == 0


def test_single_if_is_one():
    src = b'''
    class Foo {
      void m(int a) {
        if (a > 0) { print(1); }
      }
    }
    '''
    assert complexity_of_source(src) == 1


def test_if_else_if_else_chain():
    src = b'''
    class Foo {
      void m(int a) {
        if (a > 0) { print(1); }
        else if (a < 0) { print(2); }
        else { print(3); }
      }
    }
    '''
    assert complexity_of_source(src) == 3


def test_nested_if_adds_nesting_penalty():
    src = b'''
    class Foo {
      void m(int a, int b) {
        if (a > 0) {
          if (b > 0) { print(1); }
        }
      }
    }
    '''
    assert complexity_of_source(src) == 3


def test_for_loop_and_while_loop():
    src = b'''
    class Foo {
      void m(int a) {
        for (var i = 0; i < a; i++) { print(i); }
        while (a > 0) { a--; }
      }
    }
    '''
    assert complexity_of_source(src) == 2


def test_boolean_operator_groups():
    src1 = b'class Foo { void m(bool a, bool b, bool c) { if (a && b && c) {} } }'
    src2 = b'class Foo { void m(bool a, bool b, bool c) { if (a && b || c) {} } }'
    assert complexity_of_source(src1) == 2
    assert complexity_of_source(src2) == 3


def test_ternary_adds_complexity():
    src = b'class Foo { int m(int a) { return a > 0 ? 1 : 2; } }'
    assert complexity_of_source(src) == 1


def test_try_catch_adds_complexity_per_catch():
    src = b'''
    class Foo {
      void m() {
        try { risky(); } catch (e) { print(e); }
      }
    }
    '''
    assert complexity_of_source(src) == 1


def test_top_level_function_is_scored():
    src = b'void topLevel(int a) { if (a > 0) { print(1); } }'
    assert complexity_of_source(src) == 1


def test_bodiless_constructor_scores_zero():
    src = b'class Foo { int x; Foo(this.x); }'
    assert complexity_of_source(src) == 0


def test_getter_and_arrow_body_are_scored():
    src = b'class Foo { int x; int get val => x > 0 ? x : 0; }'
    assert complexity_of_source(src) == 1


def test_closures_recurse_at_same_nesting_not_nested():
    src = b'''
    class Foo {
      void m(List<int> xs) {
        xs.forEach((x) { if (x > 0) { print(x); } });
      }
    }
    '''
    assert complexity_of_source(src) == 1
