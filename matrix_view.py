from PIL import Image, ImageDraw, ImageFont


class MatrixView:
    def __init__(
        self,
        xLen=128,
        yLen=16,
        xSize=1024,
        ySize=256,
        defaultCellColorOn=(128, 0, 0),
        defaultCellColorOff=(0, 0, 0),
        defaultTextColor=(255, 255, 255),
        defaultBorderColor=(64, 64, 64),
        fontSize=8,
        fileName='matrix.png'
    ):
        # Basic validation
        if not (16 <= xLen <= 256):
            raise ValueError("xLen must be in range 16..256")
        if not (4 <= yLen <= 16):
            raise ValueError("yLen must be in range 4..16")

        self.fileName = fileName
        self.xLen = xLen
        self.yLen = yLen
        self.xSize = xSize
        self.ySize = ySize

        self.defaultCellColorOn = defaultCellColorOn
        self.defaultCellColorOff = defaultCellColorOff
        self.defaultTextColor = defaultTextColor
        self.defaultBorderColor = defaultBorderColor
        
        self.fontSize = fontSize

        # Reserve some space at the bottom for column numbers
        self.bottomLabelHeight = int(ySize * 0.15)

        self.gridHeight = self.ySize - self.bottomLabelHeight
        self.cellWidth = self.xSize / self.xLen
        self.cellHeight = self.gridHeight / self.yLen

        # Internal state: indexed as [column][row]
        self.cellColors = [
            [self.defaultCellColorOff for _ in range(self.yLen)]
            for _ in range(self.xLen)
        ]
        self.cellTexts = [
            ["" for _ in range(self.yLen)]
            for _ in range(self.xLen)
        ]
        self.cellTextColors = [
            [self.defaultTextColor for _ in range(self.yLen)]
            for _ in range(self.xLen)
        ]

        try:
            self.font = ImageFont.truetype("DejaVuSansMono.ttf", self.fontSize)
        except IOError:
            self.font = ImageFont.truetype("DejaVuSans.ttf", self.fontSize)
    
    def setCell(self, cellColumnIdx, cellRowIdx, cellText, cellColor=None, textColor=None):
        if not (0 <= cellColumnIdx < self.xLen):
            return
        if not (0 <= cellRowIdx < self.yLen):
            return

        self.cellColors[cellColumnIdx][cellRowIdx] = (
            cellColor if cellColor is not None else self.defaultCellColorOn
        )
        self.cellTexts[cellColumnIdx][cellRowIdx] = str(cellText)
        self.cellTextColors[cellColumnIdx][cellRowIdx] = (
            textColor if textColor is not None else self.defaultTextColor
        )
    
    def clearCell(self, cellColumnIdx, cellRowIdx):
        if not (0 <= cellColumnIdx < self.xLen):
            return
        if not (0 <= cellRowIdx < self.yLen):
            return

        self.cellColors[cellColumnIdx][cellRowIdx] = self.defaultCellColorOff
        self.cellTexts[cellColumnIdx][cellRowIdx] = ""
        self.cellTextColors[cellColumnIdx][cellRowIdx] = self.defaultTextColor
        
    def _draw_rotated_text(self, base_img, position, text, angle, fill, font):
        text_bbox = font.getbbox(text)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        txt_img = Image.new("RGBA", (text_w, text_h), (0, 0, 0, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((0, 0), text, fill=fill, font=font)

        rotated = txt_img.rotate(angle, expand=True)
        base_img.paste(rotated, position, rotated)

    def draw(self):
        img = Image.new("RGB", (self.xSize, self.ySize), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Draw cells
        for col in range(self.xLen):
            for row in range(self.yLen):
                # Convert logical row index (0 = bottom) to image Y
                inv_row = self.yLen - 1 - row

                x0 = int(col * self.cellWidth)
                y0 = int(inv_row * self.cellHeight)
                x1 = int((col + 1) * self.cellWidth)
                y1 = int((inv_row + 1) * self.cellHeight)

                draw.rectangle(
                    [x0, y0, x1, y1],
                    fill=self.cellColors[col][row],
                    outline=self.defaultBorderColor,
                )

                text = self.cellTexts[col][row]
                if text:
                    bbox = draw.textbbox((0, 0), text, font=self.font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]

                    tx = x0 + (x1 - x0 - text_w) / 2
                    ty = y0 + (y1 - y0 - text_h) / 2

                    draw.text(
                        (tx, ty),
                        text,
                        fill=self.cellTextColors[col][row],
                        font=self.font,
                    )
                    
        # Draw separators every 16 steps
        separator_color = (160, 160, 160)

        for col in range(0, self.xLen + 1, 16):
            x = int(col * self.cellWidth)
            draw.line(
                [(x, 0), (x, self.gridHeight)],
                fill=separator_color,
                width=2,
            )

        # Draw column numbers at the bottom
        '''label_y0 = self.gridHeight
        for col in range(self.xLen):
            label = str(col + 1)

            x0 = int(col * self.cellWidth)
            x1 = int((col + 1) * self.cellWidth)

            bbox = draw.textbbox((0, 0), label, font=self.font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]

            tx = x0 + (x1 - x0 - text_w) / 2
            ty = label_y0 + (self.bottomLabelHeight - text_h) / 2

            draw.text((tx, ty), label, fill=self.defaultTextColor, font=self.font)
        '''
        # Draw rotated column numbers at the bottom (90°)
        label_y0 = self.gridHeight

        for col in range(self.xLen):
            label = str(col + 1)

            x_center = int((col + 0.5) * self.cellWidth)
            y_center = int(label_y0 + self.bottomLabelHeight / 2)

            # Draw rotated text centered under the column
            self._draw_rotated_text(
                img,
                position=(x_center - 6, y_center - 10),
                text=label,
                angle=90,
                fill=self.defaultTextColor,
                font=self.font,
            )
        img.save(self.fileName)
        # img.show(self.fileName)
        return img


# ------------------------------------------------------------
# Test / demo code
# ------------------------------------------------------------
if __name__ == "__main__":
    display = MatrixView(
        xLen=128,
        yLen=16,
        xSize=1920,
        ySize=320,
        fontSize=10
    )

    # Fill a few cells with hex-like labels
    for i in range(0, 32, 4):
        display.setCell(i, 0, f"{i:02X}")
        display.setCell(i + 1, 1, f"{i+1:02X}", cellColor=(0, 96, 128))
        display.setCell(i + 2, 2, f"{i+2:02X}", cellColor=(0, 128, 64))
        display.setCell(i + 3, 3, f"{i+3:02X}", cellColor=(96, 0, 128))

    display.draw()
