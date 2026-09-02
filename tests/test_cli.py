from cjdev import main


def test_main_greets(capsys):
    main()
    assert capsys.readouterr().out == "Hello, world\n"
