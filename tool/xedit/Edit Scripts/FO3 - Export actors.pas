{
  Run in FNV mode on the lab copy of Fallout3 (named FalloutNV.esm) + DLC.
  Writes lab\actors\actors.csv (NPC_/CREA base records) and lab\actors\placed.csv (ACHR/ACRE placements).
  Semicolon separated. FormIDs are written as the 6 hex digit object ID + the source plugin file name.
}
unit FO3ExportActors;

var
  base, placed: TStringList;
  nBase, nPlaced: Integer;

function ObjId(e: IInterface): string;
begin
  if Assigned(e) then Result := IntToHex(FixedFormID(e) and $FFFFFF, 6) else Result := '';
end;

function Clean(s: string): string;
begin
  Result := StringReplace(StringReplace(s, ';', ',', [rfReplaceAll]), #13#10, ' ', [rfReplaceAll]);
end;

procedure DoBase(r: IInterface);
var
  tpl, race, cls, vt, scr: IInterface;
  flags: Cardinal;
  fem: string;
begin
  flags := GetElementNativeValues(r, 'ACBS\Flags');
  if (flags and 1) <> 0 then fem := 'F' else fem := 'M';
  race := LinksTo(ElementByPath(r, 'RNAM'));
  cls := LinksTo(ElementByPath(r, 'CNAM'));
  tpl := LinksTo(ElementByPath(r, 'TPLT'));
  vt := LinksTo(ElementByPath(r, 'VTCK'));
  scr := LinksTo(ElementByPath(r, 'SCRI'));
  base.Add(Signature(r) + ';' + ObjId(r) + ';' + GetFileName(GetFile(r)) + ';' + EditorID(r) + ';' + Clean(GetElementEditValues(r, 'FULL')) + ';' + fem + ';' +
    EditorID(race) + ';' + EditorID(cls) + ';' + GetElementEditValues(r, 'ACBS\Level') + ';' + ObjId(tpl) + ';' +
    GetElementEditValues(r, 'DATA\Type') + ';' + GetElementEditValues(r, 'Model\MODL') + ';' + GetElementEditValues(r, 'NIFZ\[0]') + ';' +
    IntToStr(flags) + ';' + EditorID(scr));
  Inc(nBase);
end;

function CellOf(r: IInterface): IInterface;
var
  g: IInterface;
begin
  Result := nil;
  g := GetContainer(r);
  while Assigned(g) do begin
    if ElementType(g) = etGroupRecord then
      if (GroupType(g) = 6) or (GroupType(g) = 8) or (GroupType(g) = 9) or (GroupType(g) = 10) then begin
        Result := ChildrenOf(g);
        Exit;
      end;
    g := GetContainer(g);
  end;
end;

function WorldOf(c: IInterface): string;
var
  g: IInterface;
begin
  Result := '';
  g := GetContainer(c);
  while Assigned(g) do begin
    if ElementType(g) = etGroupRecord then
      if GroupType(g) = 1 then begin
        Result := EditorID(ChildrenOf(g)) + ':' + ObjId(ChildrenOf(g));
        Exit;
      end;
    g := GetContainer(g);
  end;
end;

procedure DoPlaced(r: IInterface);
var
  c, b: IInterface;
  rf: Cardinal;
begin
  b := LinksTo(ElementByPath(r, 'NAME'));
  if not Assigned(b) then Exit;
  c := CellOf(r);
  if not Assigned(c) then Exit;
  rf := GetElementNativeValues(r, 'Record Header\Record Flags');
  placed.Add(Signature(r) + ';' + ObjId(r) + ';' + ObjId(b) + ';' + EditorID(b) + ';' + ObjId(c) + ';' + EditorID(c) + ';' + WorldOf(c) + ';' +
    GetElementEditValues(r, 'DATA\Position\X') + ';' + GetElementEditValues(r, 'DATA\Position\Y') + ';' + GetElementEditValues(r, 'DATA\Position\Z') + ';' +
    GetElementEditValues(r, 'DATA\Rotation\X') + ';' + GetElementEditValues(r, 'DATA\Rotation\Y') + ';' + GetElementEditValues(r, 'DATA\Rotation\Z') + ';' +
    GetElementEditValues(r, 'XSCL') + ';' + IntToStr(rf) + ';' + GetFileName(GetFile(r)) + ';' + GetElementEditValues(c, 'DATA') + ';' + Clean(GetElementEditValues(c, 'FULL')));
  Inc(nPlaced);
end;

function Initialize: Integer;
var
  f, r: IInterface;
  i, j: Integer;
  sig: string;
begin
  base := TStringList.Create;
  placed := TStringList.Create;
  base.Add('sig;id;file;edid;name;sex;race;class;level;template;crtype;model;skel;acbsflags;script');
  placed.Add('sig;refid;baseid;baseedid;cellid;celledid;world;x;y;z;rx;ry;rz;scale;recflags;file;celldata;cellname');
  for i := 0 to FileCount - 1 do begin
    f := FileByIndex(i);
    if (GetFileName(f) <> 'FalloutNV.esm') and (Pos('.esm', GetFileName(f)) = 0) then Continue;
    for j := 0 to RecordCount(f) - 1 do begin
      r := RecordByIndex(f, j);
      sig := Signature(r);
      if (sig = 'NPC_') or (sig = 'CREA') then DoBase(r)
      else if (sig = 'ACHR') or (sig = 'ACRE') then DoPlaced(r);
      if (j mod 100000) = 0 then AddMessage(GetFileName(f) + ' ' + IntToStr(j) + '/' + IntToStr(RecordCount(f)) + ' base=' + IntToStr(nBase) + ' placed=' + IntToStr(nPlaced));
    end;
  end;
  ForceDirectories('X:\__CAPITAL_WORKDIR__\lab\actors\');
  base.SaveToFile('X:\__CAPITAL_WORKDIR__\lab\actors\actors.csv');
  placed.SaveToFile('X:\__CAPITAL_WORKDIR__\lab\actors\placed.csv');
  AddMessage('DONE actors base=' + IntToStr(nBase) + ' placed=' + IntToStr(nPlaced));
  Result := 0;
end;

end.
