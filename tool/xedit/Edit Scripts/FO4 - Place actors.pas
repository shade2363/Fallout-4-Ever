{
  FO4 mode, load Fallout3.esm (converted). Creates CapitalActors.esp: for each line of lab\actors\actors-map.csv
  (sorted by target cell) adds an ACHR to an override of the target cell, pointing at a Fallout4.esm leveled actor / NPC.
  Interior rows: cell by object ID. Exterior rows: cell by worldspace + map grid (gx,gy).
  Columns: key;refid;cellid;worldid;gx;gy;fo4edid;x;y;z;rx;ry;rz;scale;srcbase
  Log: lab\actors\place-log.txt
}
unit FO4PlaceActors;

var
  log: TStringList;

function FormFor(f: IInterface; hex: string): Cardinal;
begin
  Result := (MasterCount(f) shl 24) or StrToInt('$' + hex);
end;

function GetCellFromWorldspace(Worldspace: IInterface; GridX, GridY: integer): IInterface;
var
  blockidx, subblockidx, cellidx: integer;
  wrldgrup, block, subblock, cell: IInterface;
  Grid, GridBlock, GridSubBlock: TwbGridCell;
  LabelBlock, LabelSubBlock: Cardinal;
begin
  Result := nil;
  Grid := wbGridCell(GridX, GridY);
  GridSubBlock := wbSubBlockFromGridCell(Grid);
  LabelSubBlock := wbGridCellToGroupLabel(GridSubBlock);
  GridBlock := wbBlockFromSubBlock(GridSubBlock);
  LabelBlock := wbGridCellToGroupLabel(GridBlock);
  wrldgrup := ChildGroup(Worldspace);
  for blockidx := 0 to Pred(ElementCount(wrldgrup)) do begin
    block := ElementByIndex(wrldgrup, blockidx);
    if GroupLabel(block) <> LabelBlock then Continue;
    for subblockidx := 0 to Pred(ElementCount(block)) do begin
      subblock := ElementByIndex(block, subblockidx);
      if GroupLabel(subblock) <> LabelSubBlock then Continue;
      for cellidx := 0 to Pred(ElementCount(subblock)) do begin
        cell := ElementByIndex(subblock, cellidx);
        if (Signature(cell) <> 'CELL') or GetIsPersistent(cell) then Continue;
        if not Assigned(ElementByPath(cell, 'XCLC')) then Continue;
        if (GetElementNativeValues(cell, 'XCLC\X') = Grid.x) and (GetElementNativeValues(cell, 'XCLC\Y') = Grid.y) then begin
          Result := cell;
          Exit;
        end;
      end;
      Break;
    end;
    Break;
  end;
end;

function Initialize: Integer;
var
  lines, p: TStringList;
  fo3, fo4, out, cell, cellOvr, ref, tgt, wrld: IInterface;
  i, ok, noCell, noTarget, noRef, nCells: Integer;
  curKey: string;
begin
  log := TStringList.Create;
  lines := TStringList.Create;
  lines.LoadFromFile('X:\__CAPITAL_WORKDIR__\lab\actors\actors-map.csv');
  p := TStringList.Create;
  p.Delimiter := ';';
  p.StrictDelimiter := True;
  fo3 := nil; fo4 := nil;
  for i := 0 to FileCount - 1 do begin
    if GetFileName(FileByIndex(i)) = 'Fallout3.esm' then fo3 := FileByIndex(i);
    if GetFileName(FileByIndex(i)) = 'Fallout4.esm' then fo4 := FileByIndex(i);
  end;
  if (not Assigned(fo3)) or (not Assigned(fo4)) then begin
    AddMessage('Fallout3.esm / Fallout4.esm not loaded'); Result := 1; Exit;
  end;
  out := AddNewFileName('CapitalActors.esp', False);
  SetElementNativeValues(ElementByIndex(out, 0), 'HEDR\Next Object ID', $800);
  AddMasterIfMissing(out, 'Fallout4.esm');
  AddMasterIfMissing(out, 'Fallout3.esm');
  ok := 0; noCell := 0; noTarget := 0; noRef := 0; nCells := 0; curKey := ''; cellOvr := nil;
  for i := 1 to lines.Count - 1 do begin
    p.DelimitedText := lines[i];
    if p.Count < 14 then Continue;
    if p[0] <> curKey then begin
      curKey := p[0];
      cellOvr := nil;
      if p[3] = '' then
        cell := RecordByFormID(fo3, FormFor(fo3, p[2]), True)
      else begin
        wrld := RecordByFormID(fo3, FormFor(fo3, p[3]), True);
        if Assigned(wrld) then cell := GetCellFromWorldspace(wrld, StrToInt(p[4]), StrToInt(p[5])) else cell := nil;
      end;
      if Assigned(cell) and (p[3] <> '') and (not Assigned(ElementByPath(cell, 'XCLC'))) then begin
        log.Add('exterior cell without grid skipped: ' + Name(cell));
        cell := nil;
      end;
      if Assigned(cell) then begin
        cellOvr := wbCopyElementToFile(cell, out, False, True);
        Inc(nCells);
      end;
      if log.Count < 12 then log.Add(curKey + ' cell=' + IntToStr(Ord(Assigned(cell))) + ' override=' + IntToStr(Ord(Assigned(cellOvr))));
    end;
    if not Assigned(cellOvr) then begin
      Inc(noCell);
      Continue;
    end;
    // placed actors must be NPC_ records (an ACHR pointing at a leveled list crashes the game at load)
    tgt := MainRecordByEditorID(GroupBySignature(fo4, 'NPC_'), p[6]);
    if not Assigned(tgt) then begin
      Inc(noTarget);
      Continue;
    end;
    ref := nil;
    try
      ref := Add(cellOvr, 'ACHR', True);
    except
      ref := nil;
    end;
    if not Assigned(ref) then begin
      Inc(noRef);
      Continue;
    end;
    try
      SetElementNativeValues(ref, 'NAME', FixedFormID(tgt));
      Add(ref, 'DATA', True);
      SetElementEditValues(ref, 'DATA\Position\X', p[7]);
      SetElementEditValues(ref, 'DATA\Position\Y', p[8]);
      SetElementEditValues(ref, 'DATA\Position\Z', p[9]);
      SetElementEditValues(ref, 'DATA\Rotation\X', p[10]);
      SetElementEditValues(ref, 'DATA\Rotation\Y', p[11]);
      SetElementEditValues(ref, 'DATA\Rotation\Z', p[12]);
      if (p[13] <> '') and (p[13] <> '1.000000') then begin
        Add(ref, 'XSCL', True);
        SetElementEditValues(ref, 'XSCL', p[13]);
      end;
    except
      Inc(noRef);
      if log.Count < 40 then log.Add('failed ref ' + p[1] + ' in ' + p[0] + ' cell ' + Name(cellOvr));
      try
        Remove(ref);
      except
      end;
      Continue;
    end;
    Inc(ok);
    if (ok mod 250) = 0 then AddMessage('placed ' + IntToStr(ok) + ' in ' + IntToStr(nCells) + ' cells');
  end;
  log.Add('placed=' + IntToStr(ok) + ' cells=' + IntToStr(nCells) + ' noCell=' + IntToStr(noCell) + ' noTarget=' + IntToStr(noTarget) + ' noRef=' + IntToStr(noRef));
  log.SaveToFile('X:\__CAPITAL_WORKDIR__\lab\actors\place-log.txt');
  AddMessage('DONE placed=' + IntToStr(ok) + ' noCell=' + IntToStr(noCell) + ' noTarget=' + IntToStr(noTarget) + ' noRef=' + IntToStr(noRef));
  Result := 0;
end;

end.
