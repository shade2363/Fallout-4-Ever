{
  Run in FO4 mode loading only Fallout4.esm (+DLC). Lists NPC_ and LVLN records:
  sig;formid8;edid;full;race;template  ->  lab\actors\fo4_actors.csv
}
unit FO4ListActors;

function Initialize: Integer;
var
  f, r: IInterface;
  i, j: Integer;
  sl: TStringList;
  sig: string;
begin
  sl := TStringList.Create;
  sl.Add('sig;formid;edid;full;race;file');
  for i := 0 to FileCount - 1 do begin
    f := FileByIndex(i);
    if Copy(GetFileName(f), 1, 3) = 'DLC' then Continue;
    for j := 0 to RecordCount(f) - 1 do begin
      r := RecordByIndex(f, j);
      sig := Signature(r);
      if (sig = 'NPC_') or (sig = 'LVLN') then
        sl.Add(sig + ';' + IntToHex(FixedFormID(r), 8) + ';' + EditorID(r) + ';' + GetElementEditValues(r, 'FULL') + ';' + EditorID(LinksTo(ElementByPath(r, 'RNAM'))) + ';' + GetFileName(GetFile(r)));
    end;
  end;
  ForceDirectories('X:\__CAPITAL_WORKDIR__\lab\actors\');
  sl.SaveToFile('X:\__CAPITAL_WORKDIR__\lab\actors\fo4_actors.csv');
  AddMessage('DONE fo4 actors ' + IntToStr(sl.Count));
  Result := 0;
end;

end.
