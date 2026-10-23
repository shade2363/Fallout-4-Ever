{
  Fallout4.esm NPC_ records with their template (TPLT) and flags: lab\actors\fo4_npc_templates.csv
  columns: edid;full;tplt_sig;tplt_edid;unique(flag);essential;protected;template_flags
}
unit FO4ListNpcTemplates;

function Initialize: Integer;
var
  f, r, t: IInterface;
  i, j: Integer;
  sl: TStringList;
  tsig, tedid: string;
begin
  sl := TStringList.Create;
  sl.Add('edid;full;tpltsig;tpltedid;acbs;templateflags');
  for i := 0 to FileCount - 1 do begin
    f := FileByIndex(i);
    if GetFileName(f) <> 'Fallout4.esm' then Continue;
    for j := 0 to RecordCount(f) - 1 do begin
      r := RecordByIndex(f, j);
      if Signature(r) <> 'NPC_' then Continue;
      t := LinksTo(ElementByPath(r, 'TPLT'));
      tsig := ''; tedid := '';
      if Assigned(t) then begin
        tsig := Signature(t);
        tedid := EditorID(t);
      end;
      sl.Add(EditorID(r) + ';' + GetElementEditValues(r, 'FULL') + ';' + tsig + ';' + tedid + ';' + GetElementEditValues(r, 'ACBS\Flags') + ';' + GetElementEditValues(r, 'ACBS\Template Flags'));
    end;
  end;
  ForceDirectories('X:\__CAPITAL_WORKDIR__\lab\actors\');
  sl.SaveToFile('X:\__CAPITAL_WORKDIR__\lab\actors\fo4_npc_templates.csv');
  AddMessage('DONE npc templates ' + IntToStr(sl.Count));
  Result := 0;
end;

end.
